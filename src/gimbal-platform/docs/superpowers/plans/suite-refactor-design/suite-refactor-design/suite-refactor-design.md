# Suite 层重构设计方案 — UI · 交互 · 功能

2026-10-09 · 基线 `feat/plate-s1` @ `643a14b`(权限域二期 P2 后端已落地)

Suite 合并为一个实体:新建走画布从零搭建、模式由结构推断,编辑走管理页做局部调整;聚合沿用现有批次通道,串联、扇出、依赖编排由服务端拼装 graph 走一次编排执行。本方案建立在已落地的 P2(引用分享、发布联动、处置引用处理)之上,保留其读 / 运行 / 发布语义。原型图见下文 [原型图与说明](#prototypes)(图片在 `prototypes/` 目录,离线可交互版本在 `prototype-src/`,用法见文末「附录」);本版相对评审稿的改动见文末「修订记录」。

## 结论与范围

现有的「用例组」(`/suites`,成员层 + 聚合批量运行)和「Suite 编排」(`/suites/composer`,一次性 graph 编排)做的是同一件事的两半,本方案把它们合成一个 Suite。

- **一个实体**:Suite = 一组场景(成员层) + 它们怎么跑(编排层)。侧栏只留一个「Suite」入口,`/suites/composer` 与 `SuiteComposer.vue` 删除。
- **两条路径**:新建时用户还没有结构,给一张画布从零搭,模式由画出来的结构推断;编辑已有 Suite 时多是局部调整,给管理页。
- **两条运行通道(已定)**:聚合保留现有批次通道,逐成员按默认方案发起、共用 batch_id,完整支持多行数据集与注入;串联、扇出、依赖编排由服务端从 Suite 拼装 graph,走一次编排执行,每个单元只跑一行数据(原因见「概念模型」约束 5)。三处「运行」都先过预检。
- **与 P2 共存**:P2 后端已落地 —— Suite 有可见性(私有 / 公共)、可被引用分享或拷贝分享、可发布 / 下架,运行闸已换成 `can_run_scenario` / `can_run_suite`。重构后的页面与接口必须承接这些语义:非属主看到只读态,公共 Suite 的成员约束、拷贝时的编排配置重映射都要随新模型调整(见「概念模型 · 访问角色」与「交互规则 · P2 权限、分享与发布」)。
- **不做兼容**:Suite 目前只是预埋功能、未正式使用,接口、表结构、路由可以直接改,不保留旧行为,不做数据迁移。

**不在本次范围**:P2 自身的前端(分享弹窗、「共享给我」清单页、浏览镜头组件本体 —— 本方案只在 Suite 页面上预留入口位与只读态)、Suite 嵌套、动态成员(路径 + 筛选器)、矩阵模式。

## 概念模型

Suite 由两层组成:成员层说「有哪些场景」,编排层说「怎么跑」;改编排不改成员。

| 层 | 内容 | 存储 |
| --- | --- | --- |
| 成员层 | 场景、角色(主体 / 前置 / 后置)、顺序 | `suite_members` 关系表,成员的唯一真相源 |
| 编排层 | 模式、依赖(needs)、单元设置、运行参数、判定门、横切断言 | `suites.mode` + `suites.mode_config`(JSON,按 scenarioId 引用成员) |

**四种结构**(与执行器 `SuiteGraph.mode` 一一对应;执行器把四种模式都编译成同一种依赖图,区别只在依赖从哪来):

| 界面名 | 执行器 mode | 画布上的结构 | 运行通道 | 典型用途 |
| --- | --- | --- | --- | --- |
| 聚合 | `aggregate` | 只拖入、不连线 | 批次:每个成员一条独立执行 | 冒烟集、回归集 |
| 串联 | `chain` | 连成一条直线 | 一次编排执行;可只跑到某一步 | 下单 → 支付 → 退款这类业务流程 |
| 扇出 | `fanout` | 一个源指向其余全部 | 一次编排执行 | 一次登录后打多个接口 |
| 依赖编排 | `compose` | 其他无环结构(分叉、汇合) | 一次编排执行 | 先准备数据,再多路并行,最后汇总 |

四种结构在画布和管理页上的样子见原型 [11](#proto-11)、[20](#proto-20)。

**建模约束**:

1. **前置 / 后置也是成员**(`role` = `before` / `after`),不另存在编排配置里。这样「只能放自己的场景」的库层组合外键自动覆盖它们,也顺带解决了原设计「模式引用如何进入成员面」的待决项。成员统计只数 `main`。前置 / 后置只在编排模式下生效 —— 这是平台侧裁剪(聚合通道只对 `main` 成员分发),不是执行器限制:执行器调度不分模式,aggregate 下 before / after 同样会执行。
2. **一个场景只出现一次**(保持现有主键),需要多跑用单元的 ×重复。单元别名 `ref` 默认由 scenarioId 派生,可改,在 Suite 内唯一;配置里的依赖按 scenarioId 存,下发执行器时换成 ref。
3. **顺序有语义,needs 只给依赖编排**:成员顺序就是聚合的发起顺序、串联的链路顺序;扇出的源固定排在第一位。执行器 `chain` 按声明顺序生成线性依赖、`fanout` 以首个单元为源,且对聚合、扇出、串联声明 needs 会直接报编译错误(`suite/modes.py`),所以保存时按识别出的结构写好顺序,下发时只有依赖编排携带 needs。
4. **一条直线就是串联**:执行器里串联就是按顺序生成的线性依赖,单元间传值在所有模式下都按全部上游自动连线,所以画成直线的依赖编排与串联运行结果相同。直线一律识别为串联,不再让用户二选一;串联额外支持「只跑到某一步」。
5. **编排模式下每个单元只跑一行数据**。数据集行 × 注入的展开是平台在单场景运行时做的(`compute_run_fanout`),执行器的场景里没有数据集;graph 的一个单元只能对应一份物化后的场景,拆成多份后 needs、串联传值、扇出的源都没有定义。所以非聚合模式的单元在 `units.<id>.row` 里选定一行(默认取方案选中的第一行),方案选了多行时预检提示只会跑所选那行。方案里的注入条目在单场景运行中是逐条展开的变体,编排模式下同样不展开;需要时在单元上显式选择(`units.<id>.injectionEntryIds`),按编排单元现有的方式(`GraphUnitSpec.injectionEntryIds`)叠加。聚合不受此限。
6. **引用随成员清理**:编排配置只按 scenarioId 引用成员。会删掉成员行的路径只有两条 —— `DELETE /suites/{id}/members/{sid}` 与场景删除(`scenario_store.delete`;PG 上由组合外键 CASCADE,SQLite 显式删除兜底)。CASCADE 只删成员行,不清 `mode_config` 里的引用、也不推进 rev,所以这两条路径都要在应用层同一事务内显式清理引用(needs、单元设置、`map`、横切断言选择器)并推进 rev;场景删除的清理写在 `scenario_store.delete` 内,单点实现,不在各调用方各写一份。用户处置不需要清理:publicize / purge 整体删除该用户的全部 Suite,transfer 把 Suite、成员、场景三处属主同一事务改写(组合外键 DEFERRED 保证不可拆分),scenarioId 不变、引用始终有效。运行方案、数据集被删时不级联改配置:`schemeId` / `row` 悬空由预检报出(复用 `_precheck_one` 的失效口径)。
7. **「开始」节点只是画面元素**:从它出发的连线不保存,没有入边的单元即入口;前置区、后置区内不能连线。
8. **编排配置随拷贝重映射**:P2 的拷贝分享(`_deep_copy_suite`)逐个复制成员场景,副本的 scenarioId 是新的。现实现注释明写「mode_config P1 恒 {} 免重映射」—— 重构后必须同时复制 `mode`、成员 `role` 与 `mode_config`,并把配置里所有 scenarioId 键与引用(units 键、needs、横切断言选择器)换成副本 id;副本 rev 归零、不是草稿;成员复制失败被跳过时按约束 6 的口径清理其引用。

**访问角色**(P2 已落地,§7.6 判定):

| 角色 | 判定 | 查看 | 运行 | 改成员 / 编排 | 发布 / 下架 | 分享 |
| --- | --- | --- | --- | --- | --- | --- |
| 属主 | `suite.owner_id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| 管理员 | `role = admin` | ✓ | ✓ | ✓(治理) | ✓(下架他人通知属主 + 审计) | ✗(不可代发) |
| 被引用者 | `share_refs.suite_id` 命中 | ✓ | ✓(引用覆盖全部成员) | ✗ | ✗ | ✗(可退订) |
| 公共读者 | `visibility = public` | ✓ | ✗(公共资源先复制再跑,不变量 7) | ✗ | ✗ | ✗ |

前端不自己推导角色:`GET /suites/{id}` 返回 `access`(`owner` / `admin` / `ref` / `public`)与能力位 `canEdit` / `canRun` / `canShare`,页面据此切换只读态。

`mode_config` 的形状:

```json
{
  "units": {
    "sc-order-create-001": {
      "ref": "order",
      "needs": ["sc-user-login-005"],
      "repeat": 1,
      "nRuns": 1,
      "schemeId": null,
      "row": {"datasetId": "ds-order-basic", "rowIndex": 0},
      "injectionEntryIds": [],
      "map": {"token": "authToken"}
    }
  },
  "parallel": 2,
  "nRuns": 1,
  "gates": [{"metric": "pass_rate", "op": "gte", "value": 1}],
  "checks": [{"on": {"bracket": "main"}, "strategy": {}}],
  "draft": false
}
```

- `schemeId` 为空表示用该场景的默认运行方案。
- `row` 只在非聚合模式下使用,为空表示不带数据集行(裸基线);键名沿用平台权威键 `datasetId`(`DataSetSelection`),行号与编辑器一致(0-based)。
- `injectionEntryIds` 只在非聚合模式下使用,条目 id 取自该场景的 assertion_registry。
- `map` 是连线改名(上游输出名 → 本地输入名),对应执行器 `UnitDecl.map`,用于消解同名输入歧义。
- `draft` 标记草稿。

## 页面流

![Suite 页面流](diagrams/page-flow.png)

列表是唯一入口:「+ 新建」进画布,行点击进管理页;完成编排后落到管理页,之后的大改结构再从管理页回到画布。列表、完成编排、管理页三处的「运行」都先进预检;聚合运行后进批次视图,其余模式进执行详情,两者的结果都回挂到运行记录。非属主(被引用者、公共读者)从列表进入的是管理页的只读态,不进入画布。各页原型见 [原型图与说明](#prototypes)。

## 原型与页面设计

共 8 个页面(另有已存在的执行详情 / 批次视图),原型在 [Suite 整合设计稿](https://claude.ai/artifact/Kggdk5yNCfGtNDhcvK5Yq1) 中按编号排列,12 和 20 两张可以点。视觉沿用 Gimbal Platform 设计系统 v2:单一 accent 色、4px 栅格、1px 边框区分层级、标识符一律等宽字体。原型画的是属主视角;P2 带来的只读态、浏览范围、发布 / 分享入口在下表「P2 补充」列与「交互规则 · P2 权限、分享与发布」中以文字为准,原型未覆盖。

| 编号 | 页面 | 建议路由 | 布局 | 关键交互 | P2 补充 | 原型 |
| --- | --- | --- | --- | --- | --- | --- |
| 02 | Suite 列表 | `/suites` | 页头 + 浏览范围 / 搜索 / 模式筛选 + 表格(Suite、模式、成员数、归属、最近运行、操作) | 「+ 新建 Suite」直接进 10;行点击进 20(最近一次失败则进 21);行内「运行」开 30;⋯ 重命名 / 复制 / 删除;草稿带「草稿」标记 | 浏览范围「我的 / 共享给我 / 公共」(默认我的,口径同场景库浏览镜头);归属列显示「引用 · 分享者」「公共」chip;行内运行按 `canRun` 显隐;草稿只出现在「我的」 | [02](#proto-02) |
| 10 | 新建 · 空白画布 | `/suites/new` | 左:我的场景抽屉;中:前置区 / 画布 / 后置区 / 结构状态条;右:三步引导 | 画布只有「开始」节点和放置框;首次进入自动弹出 11 | — | [10](#proto-10) |
| 11 | 四种结构说明 | 10 / 12 上的弹层 | 四张模式卡(缩略图、怎么画、怎么跑、适合、留意)+ 识别规则表 | 「用这个结构开始」在画布上放好骨架;可勾选不再自动弹出,状态条「?」随时再打开 | — | [11](#proto-11) |
| 12 | 新建 · 拖入与连线 | `/suites/:id/compose` | 同 10;右侧变为选中单元的检查器 | 拖入 = 加成员;从节点右侧圆点拉线 = 加 needs;状态条实时显示识别结果和一句理由;连出环就地拒绝;检查器改 ref、×重复、runs、运行方案,编排模式下另选数据行与注入条目 | 仅 `canEdit`;非属主访问该路由重定向到 20 只读态;公共 Suite 拖入私有场景先弹发布确认 | [12 · 四步](#proto-12) |
| 13 | 连线检查与完成 | 同 12,弹层 | 画布 + 连线检查器 + 完成面板 | 直线结构识别为串联,可设「只跑到某一步」;选中连线看传递的变量与悬空引用,同名歧义在此改名(写 `map`);试跑选中段(所选单元 + 其上游);「完成编排」填名称 + 选保存后去 20 或 30 | — | [13](#proto-13) |
| 20 | 管理页 · 编排 | `/suites/:id` | 页头(名称、归属 / 可见性标记、运行按钮含通道说明、⋯ 菜单)+ 页签 + 模式条 + 三栏(场景抽屉 / 前置·主体·后置 / 运行参数·判定门·横切断言) | 成员增删、拖拽或 ▲▼ 排序;显式切换模式;主体区按模式呈现(列表 / 链 / 源 + 变体 / 分层 DAG);聚合下判定门与前置 / 后置只读并说明;「在画布中改结构」进 12 | 只读态:隐藏场景抽屉、排序与模式条操作,右栏只读,页头横幅说明来源(「来自 X 的引用分享」/「公共 Suite」);被引用者保留「运行」,另有「转为副本」(复用现有 `POST /shares/{id}/fork`,suite 引用已支持,零后端改动)与「退订」;公共读者换为「复制到我的」;属主 ⋯ 菜单含「发布 / 下架」「分享」(分享弹窗属 P2 前端,本次只留入口位);公共 Suite 页头常驻「公共」标记 | [20 · 四模式](#proto-20) |
| 21 | 管理页 · 运行记录 | `/suites/:id?tab=runs` | 最近 12 次结果条 + 历次运行表(批次与编排执行混排,标明通道与发起人) | 筛选失败 / 我发起的;展开看逐单元结果、判定门实测值;跳批次视图或执行详情;定位到 20 的对应成员;只重跑失败单元 | 属主 / 管理员看全部发起人的运行;被引用者只看自己发起的;公共读者无发起记录,runs 页签隐藏或空态提示「复制到我的后可运行」;「只重跑失败单元」只对自己发起的执行开放(属主 / 管理员不限) | [21](#proto-21) |
| 30 | 运行预检 | 弹窗 | 摘要(单元数、预计 runs / 上限、判定门数)+ 逐条预检 | 在途批次或运行 → 按钮变「查看」;超上限 → 禁用并列出前三大来源;方案多行但只会跑一行 → 警告并直达单元改选;预检警告可直达对应成员 | 编排模式下有不可运行的单元 → 整体禁用并列出(图里不能跳过单元);认证别名在发起人名下解不到 → 警告(见「风险」) | [30](#proto-30) |

反向入口保留现有实现:场景库批量勾选 →「加入 Suite」,场景详情「所属 Suite」→ 20 并高亮该成员。

<a id="prototypes"></a>

### 原型图与说明

每张图下列出要看的要点,以及它对应的规则章节。

<a id="proto-00"></a>

#### 00 整合总览

![00 整合总览](prototypes/00-overview.png)

- 重叠分析表:左两列是现状(用例组、Suite 编排),右列是整合后的落点,对应「结论与范围」「概念模型」。
- 新信息架构主路径与三张决策卡。
- 源文件:`prototype-src/Main.dc.html`

<a id="proto-01"></a>

#### 01 交互说明

![01 交互说明](prototypes/01-interaction-spec.png)

- 页面流、页面清单(路由 / 进入 / 操作 / 去向)、六组交互规则、后端依赖、决策记录,是本文档的画板版摘要(P2 补充未进画板,以本文为准)。
- 源文件:`prototype-src/InteractionSpec.dc.html`

<a id="proto-02"></a>

#### 02 Suite 列表

![02 Suite 列表](prototypes/02-suite-list.png)

- 侧栏只剩一个「Suite」入口;表格含模式、成员数、最近运行。
- 「+ 新建 Suite」进 [10](#proto-10);行点击进 [20](#proto-20);行内「运行」开 [30](#proto-30)。
- 原型未画浏览范围切换与归属列,见页面表「P2 补充」。
- 源文件:`prototype-src/SuiteList.dc.html`

<a id="proto-10"></a>

#### 10 新建 · 空白画布

![10 新建 · 空白画布](prototypes/10-compose-empty.png)

- 画布只有「开始」节点和放置框;右侧是三步引导;状态条「?」打开 [11](#proto-11)。
- 规则见「交互规则 · 新建:何时成为一个 Suite」:此时还不落库,首次拖入才创建草稿。
- 源文件:`prototype-src/ComposeEmpty.dc.html`

<a id="proto-11"></a>

#### 11 四种结构说明

![11 四种结构说明](prototypes/11-structure-guide.png)

- 四张模式卡:缩略图、怎么画、怎么跑、适合、留意;下方是识别规则表。
- 对应「概念模型」的四种结构表与约束 4、5,以及「交互规则 · 新建:模式由结构推断」。
- 源文件:`prototype-src/ComposeModes.dc.html`

<a id="proto-12"></a>

#### 12 新建 · 拖入与连线(四步)

![12 第 1 步 空白](prototypes/12-compose-step1-empty.png)

![12 第 2 步 拖入入口,识别为聚合](prototypes/12-compose-step2-entry.png)

![12 第 3 步 从 login 拉出两条线,识别为扇出](prototypes/12-compose-step3-fanout.png)

![12 第 4 步 汇合到支付,识别为依赖编排,成环连线被拒](prototypes/12-compose-step4-compose.png)

- 第 1 → 4 步:空白 → 拖入 login(聚合)→ 拉出两条线(扇出,虚线是正在拖入的 pay)→ 汇合到 pay(依赖编排),pay → login 的连线因成环被拒绝。
- 底部状态条随每一步给出识别结果和一句理由;右侧检查器含「数据行」选择(约束 5)。
- 对应「交互规则 · 新建:模式由结构推断」;离线查看时顶部「上一步 / 下一步」可切换四步。
- 源文件:`prototype-src/Compose.dc.html`

<a id="proto-13"></a>

#### 13 新建 · 连线检查与完成

![13 新建 · 连线检查与完成](prototypes/13-compose-finish.png)

- 直线结构直接识别为串联,可设「只跑到某一步」(约束 4)。
- 右上连线检查器:传递的变量、未被引用的产出、悬空引用;同名改名写入单元的 `map`。下方「完成编排」面板:命名、保存后去 [20](#proto-20) 或 [30](#proto-30)。
- 「试跑选中段(含上游)」对应 `control.only`。
- 源文件:`prototype-src/ComposeFinish.dc.html`

<a id="proto-20"></a>

#### 20 管理页 · 编排(四种模式)

![20 聚合](prototypes/20-manage-aggregate.png)

![20 串联](prototypes/20-manage-chain.png)

![20 扇出](prototypes/20-manage-fanout.png)

![20 依赖编排](prototypes/20-manage-compose.png)

- 同一组成员在四种模式下的主体区:聚合是列表(显示默认方案),串联是链(可只跑到某一步),扇出是源 + 变体(×重复),依赖编排是分层 DAG。
- 右侧运行参数、判定门、横切断言;聚合下判定门置灰。
- 对应「交互规则 · 编辑:管理页的模式切换」;离线查看时模式条可切换。
- 原型是属主视角;只读态见页面表「P2 补充」。
- 源文件:`prototype-src/Workspace.dc.html`

<a id="proto-21"></a>

#### 21 管理页 · 运行记录

![21 管理页 · 运行记录](prototypes/21-manage-runs.png)

- 最近 12 次结果条;批次与编排执行混排并标明通道。
- 展开一次失败的编排执行:逐单元结果、判定门实测值、「只重跑失败单元」。对应「交互规则 · 运行」。
- 源文件:`prototype-src/RunHistory.dc.html`

<a id="proto-30"></a>

#### 30 运行预检

![30 运行预检](prototypes/30-run-preflight.png)

- 主图是依赖编排模式的预检:单元数、预计 runs、判定门数、逐条预检,含「只会跑 1 行数据」的警告(约束 5)。
- 右侧三张是聚合模式的分支:已有进行中的批次、超上限、部分成员未发起。对应「交互规则 · 运行」。
- 源文件:`prototype-src/RunConfirm.dc.html`

## 交互规则

**新建:何时成为一个 Suite**(原型 [10](#proto-10)、[12 第 1–2 步](#proto-12))

1. 打开 10 不落库;首次拖入场景时创建草稿 Suite,URL 换成 `/suites/:id/compose`,之后每次改动自动保存(防抖 800ms)。
2. 草稿名由服务端生成且不重名(「未命名 Suite 2」…),正式名称在「完成编排」时填;同名冲突留在弹层内提示。
3. 草稿不计入每人 50 个 Suite 的上限(创建、拷贝分享两处上限检查同口径);30 天未改动的空草稿(无主体成员)自动清理。平台现状只有启动期的工件清扫、没有周期任务基建,清理实现为后端 lifespan 挂一个轻量循环任务(与已在 lifespan 启动的执行队列 worker 同一模式;小时级巡检 + 30 天窗口判定,删除幂等,多进程并发执行无害),不为此新引调度框架。
4. 离开画布不丢:草稿出现在列表「我的」里,点开回到 12。草稿可以运行(试跑),但不进入工作台卡片和通知汇总;草稿不能发布、不能分享。

**新建:模式由结构推断**(原型 [11](#proto-11)、[12 第 2–4 步](#proto-12)、[13](#proto-13))(自上而下,命中第一条即止;每次拖入或连线后重算;「开始」节点的连线不参与)

| 画布上的结构 | 识别为 |
| --- | --- |
| 没有任何连线(含只有一个单元) | 聚合 |
| 全部单元连成一条直线 | 串联(与画成直线的依赖编排运行结果相同,见「概念模型」约束 4) |
| 恰有一个单元指向其余全部,其余之间无连线 | 扇出(该单元为源) |
| 其他无环结构 | 依赖编排 |
| 部分相连、部分孤立 | 依赖编排,状态条提示孤立单元数,以防漏连 |

保存时按识别结果写成员顺序:串联按链路先后,扇出把源排在第一位。连线时本地即做环检测,成环的线不落下并就地提示;节点间变量是否接得上(悬空引用、同名歧义)由服务端校验返回,标在节点和连线上,不阻止保存。

**编辑:管理页的模式切换**(原型 [20](#proto-20))

- 管理页保留显式模式切换,切换不改成员。
- 切到聚合会丢弃已有 needs,前置 / 后置也不再生效:先弹确认,列出受影响的连线和单元;切到串联按当前顺序重建链;切到扇出以第一位成员为源。
- 从聚合切到编排模式时,方案选了多行数据的成员会被标出,需在单元上选定一行(默认第一行)。
- 大改依赖结构时用「在画布中改结构」进 12,保存后回 20。

**运行**(原型 [30](#proto-30)、[21](#proto-21))

- 列表、完成编排、管理页三处「运行」都先开 30 预检;预检发现本人在该 Suite 上有未结束的批次或运行,按钮直接变「查看」。
- 聚合运行后进批次视图;其余模式进执行详情。结果都回挂到 21;预检或运行中被跳过的单元,原因以页内横幅保留在 21,不只用 toast。
- 编排执行在执行记录里标为「Suite 运行」,显示 Suite 名,不计入任何成员场景的执行历史和健康趋势;在执行记录里对它点「重跑」,改为重新运行该 Suite(经过预检)。
- 试跑选中段:在画布上选中若干单元,运行这些单元及其全部上游(下发执行器 `control.only`,make 语义),串联、扇出、依赖编排通用;聚合下即只发起所选成员。串联另有「只跑到某一步」(`control.to_node`)。不提供「从中间某步开始」:执行器的 `from_node` 切片要求被跳过的上游输出由外部提供,平台无从提供。
- 只重跑失败单元:同样用 `control.only` 指向失败单元,执行器会连带重跑它们的上游以拿到输入。

**成员与权限**

- 抽屉只列「我的场景」;库层组合外键保证 Suite 只放属主自己的场景,前置 / 后置同样受约束。
- 一个场景可属于多个 Suite;场景删除后自动退出所有 Suite,并清理编排配置里的引用、推进 rev(约束 6)。

**P2 权限、分享与发布**(原型未覆盖,以本节为准)

- **只读态**:`canEdit = false` 时管理页进入只读态(见页面表「P2 补充」),画布路由 `/suites/:id/compose` 重定向到 20;页头横幅说明来源,被引用者另有「退订」与「转为副本」(`POST /shares/{id}/fork`,现有端点,零后端改动)。只读态下预检、运行记录照常可用(按各自权限)。
- **运行**:被引用者可运行(引用覆盖全部成员,`run_suite` 逐成员 `can_run_scenario` 复核);公共读者不可运行,按钮换为「复制到我的」,复制后跳到副本的管理页。编排模式下若有单元不可运行,预检整体禁用并列出这些单元 —— 图不能像聚合那样跳过单个成员;聚合保持现状(不可运行的成员记为 `not_runnable` 跳过)。
- **公共 Suite 的成员约束**:公共 Suite 加入私有场景(管理页加成员、画布拖入、反向入口「加入 Suite」三处一致)先弹确认「这些成员及其数据集将一并公开」,确认后带 `publishUnpublished` 重提;不确认则不加入。移除成员不改变该场景自己的公共状态。成员场景被下架时后端已连带下架所属公共 Suite,属主进入管理页时以横幅说明「因成员 X 下架,本 Suite 已转为私有」。
- **发布 / 下架**:属主或管理员在 20 页头 ⋯ 菜单操作;发布确认框列出将被级联公开的成员(后端回执 `publishedMembers`)。草稿不可发布,菜单项禁用并说明「完成编排后可发布」。
- **分享**:属主在 20 页头 ⋯ 菜单进入分享(引用 / 拷贝,弹窗属 P2 前端);草稿不可分享。拷贝分享得到的副本带完整编排配置(约束 8)。
- **删除**:Suite 有引用者时,删除确认框提示「N 位引用者将失去访问」;删除后通知引用者(与处置路径 `share_ref_resource_deleted` 同口径),引用行随外键级联删除。
- **运行记录可见性**:属主 / 管理员看全部发起人;被引用者只看自己发起的;公共读者无发起记录,21 的 runs 页签隐藏或空态提示「复制到我的后可运行」。防重仍按 (Suite, 发起人)。

**页面状态**

- 空:列表空态引导新建;画布空态只有「开始」和放置框;管理页无主体成员时运行按钮禁用。
- 加载 / 失败:沿用平台列表页的加载与重试样式;非读者访问返回 404(P2 口径:不可见即 404),页面按「不存在」处理。
- 并发编辑:保存带版本号,任何改动成员或编排的接口(含反向入口加成员)都推进版本号;场景删除这一非接口路径同样推进(在 `scenario_store.delete` 内显式做,FK CASCADE 不代劳,见约束 6)。画布自动保存遇到冲突时先拉取最新成员,再把本地连线合并上去;合并不了才提示「已被修改,刷新后再改」。只读态的页面收到 rev 变化时静默刷新。

## 功能与接口

后端改动集中在 `routers/suites.py`、`routers/shares.py` 的 Suite 拷贝、`services/graph_dispatch.py`、`run_dispatcher.py` 的 graph 分支,以及执行记录的归属标记;执行器已具备四种模式、前后置、判定门、`only` / `to_node` 两种裁剪和编译期校验,基本不用改。

**数据模型(迁移 0014,无数据迁移;0013 已被 shares 占用)**

- `suite_members` 加 `role`(`main` / `before` / `after`,默认 `main`)。
- `suites` 加 `rev`(乐观锁);`mode` 存解析后的模式;`mode_config` 按「概念模型」一节的形状写入。`visibility` 与 `forked_from_*` 已由 P1 / P2 提供,不动。
- `executions` 加 `kind`(`scenario` / `suite_graph`,默认 `scenario`)和可空的 `suite_id`。编排执行写 `suite_graph`;聚合批次里的每条执行仍是 `scenario`(它就是该场景按默认方案的一次真实运行),只多记 `suite_id`。注意这与队列层 `execution_jobs.kind`(`cases` / `graph` / `debug`)同名不同层、值域互斥,模型注释里点破以免混淆。
- `executions.scenario_id` 是 NOT NULL:编排执行写占位值 `suite-<suiteId>`(非 `sc-` 前缀),`scenario_name` 写 Suite 名。这样即使某处场景维度查询漏加 `kind` 过滤,也不会命中任何真实场景。
- 编排执行的快照不存首单元场景:`dispatch_run` 现状把顶层场景 payload 存进 `execution_snapshots`,suite_graph 执行若沿用会得到「第一个单元的场景」快照,详情页快照抽屉会展示误导内容。suite_graph 执行的快照改存 graph 拼装产物(或 Suite 摘要),`GET /executions/{id}/scenario-snapshot` 读侧按 `kind` 区分。

**API**

| 接口 | 变化 | 作用 | 现有基础 |
| --- | --- | --- | --- |
| `GET /suites` | 改 | 增加最近运行摘要、草稿标记、`access` / `visibility`;草稿不计入上限、只在属主的「我的」出现;`scope` 在 P2 的 `mine` / `all`(all = 公共 ∨ 自己的 ∨ 被引用的)之外补 `shared`(被引用的)/ `public`(公共)两档,支撑 02 的三档浏览范围(列表走服务端分页,客户端过滤不可行) | `list_suites` / `create_suite` 的上限检查 |
| `POST /suites` | 改 | 名称可省略,服务端生成不重名的草稿名 | `create_suite` |
| `GET /suites/{id}` | 改 | 返回成员(含 role)+ 编排配置 + rev + `access` 与能力位 `canEdit` / `canRun` / `canShare`;读闸保持 `_require_read_async` | `get_suite` |
| `PUT /suites/{id}/composition` | 新 | 整体保存模式、成员及顺序、编排配置;写闸 `_require_write`;带 rev,冲突返回 409 并附最新内容;校验配置引用都是成员、ref 唯一、顺序符合模式、`map` 目标是该单元的输入;公共 Suite 新增私有成员走与加成员同一套 `suite_member_publish_required` / `publishUnpublished` | 替代 `members/order`;`add_members` 的公共不变量分支 |
| `PATCH /suites/{id}` | 保留 | 名称、描述;完成编排时清除草稿标记 | `patch_suite` |
| `DELETE /suites/{id}` | 改 | 有引用者时删除前通知引用者 | `delete_suite`;`share_refs.suite_id` 外键 CASCADE |
| `POST /suites/{id}/members` | 改 | 反向入口批量加入,追加到主体末尾;推进 rev;公共不变量分支保留 | `add_members` |
| `DELETE /suites/{id}/members/{sid}` | 改 | 同一事务清理配置里的引用;推进 rev | `remove_member` |
| `PATCH /suites/{id}/members/order` | 删 | 并入 composition | — |
| `POST / DELETE /suites/{id}/publish` | 改 | 草稿拒绝(409 `suite_is_draft`);其余保持 P2 | `publish_suite` / `unpublish_suite` |
| `POST /suites/{id}/fork` | 新 | 公共读者「复制到我的」:深拷贝为自己名下的私有 Suite(含编排配置重映射,约束 8);读闸 + 公共可见 | 复用 `_deep_copy_suite` |
| `POST /shares`(suite) | 改 | 草稿拒绝;拷贝分享补 `mode` / `role` / `mode_config` 重映射,上限检查不计草稿 | `shares.py` `_deep_copy_suite` |
| `POST /suites/{id}/validate` | 新 | 不入队的预检,闸与运行相同(`_require_run_async`)。聚合按现有口径算总 runs、逐成员可运行性;编排模式拼装 graph 交执行器编译,报环、needs、输入是否有上游供给或歧义(歧义用单元的 `map` 改名解决)、每条连线传的变量、多行方案只跑一行的提示、不可运行的单元、在发起人名下解不到的认证别名;都返回在途批次或运行。逐成员可运行性(方案本体 / 失效数据集 / 悬空注入 / 未绑定服务)复用 `run_precheck._precheck_one`,失效判定保持服务端唯一实现、不另写一份 | 执行器 `compiler/pipeline.py` 的 `CYCLE` / `INPUT_UNSATISFIED` / `INPUT_AMBIGUOUS`;`compile_target` + `p_validate`(只编译不入队;注意 `run launch --dry-run` 在 schema 校验前就退出、只打印 payload,编译错误不会暴露,不能用作依据);`compute_run_fanout`;`run_precheck._precheck_one` |
| `POST /suites/{id}/run` | 改 | 运行闸 `_require_run_async`。聚合:现有循环分发不变(含逐成员 `can_run_scenario`,不过即 `not_runnable` 跳过);编排模式:逐单元 `can_run_scenario`,任一不过整体 403 并列出单元,通过则服务端从 Suite 拼 graph(每单元内联所选一行)→ 一次编排执行,可带 `only`(试跑选中段)或 `toNode`(串联只跑到某一步)。两者都用 batch_id `suite-<sid>-<uid>-<uuid>`,沿用按 (Suite, 发起人) 防重;顺手修正 409 `suite_run_in_progress` 链接参数 `batchId=` → `batch_id=` | `run_suite` + `graph_dispatch` |
| `GET /suites/{id}/runs` | 新 | 该 Suite 的历次运行:聚合按批次归并,编排执行逐条;含判定门结论与发起人。属主 / 管理员看全部,被引用者只看自己发起的 | `executions.suite_id` |
| `GET /executions/{id}/units` | 新 | 编排执行的逐单元结果 | 需 graph 执行逐单元落台账 |
| `GET /executions`(及场景维度的统计) | 改 | 场景维度的查询排除 `kind = suite_graph` | `routers/executions.py` 按 `scenario_id` 过滤处 |
| `POST /executions/{id}/rerun` | 改 | `suite_graph` 执行不再按 config 重放(现在会只重跑第一个场景),返回 409 并附 Suite 链接,前端转去运行该 Suite | `rerun_execution` |
| `POST /suites/{id}/runs/{executionId}/rerun-failed` | 新 | 只重跑某次编排执行里失败的单元:以失败单元为 `only` 重新运行(上游随之重跑);需运行权限,被引用者只能对自己发起的执行操作 | 执行器 `Control.only` |
| `POST /runs {graph}` | 收口 | 不再供前端直接拼 graph;Suite 运行只走 `/suites/{id}/run`。graph 授权闸 P2 已换为逐单元 `can_run_scenario`,保留供内部复用 | `runs.py` |
| `GET /scenarios/{id}/suites` | 保留 | 场景详情「所属 Suite」 | `suites_of_scenario` |

**编排通道需要补的六处**

1. **内联单行方案**:`resolve_graph_units` 现在固定调用 `_compose_scenario(payload, {})`,只跑裸基线;改为按单元方案(默认方案或 `schemeId`)取 `row` 指定的那一行合入,并带上方案的服务绑定。
2. **控制透传**:`GraphSpec` 增加 `control {only, toNode}`;拼装侧 `materialize_graph` 是手工挑键组装,须同步在产出的 graph dict 里显式写 `control` 键 —— 只改 schema 字段不会自动透过去。执行器 `Control` 实为 `{only, fromNode, toNode}` 三字段,`from_node` 切片要求被跳过的上游输出由外部提供,平台不开放:拼装处显式不透传 `fromNode`,只落 `only` / `toNode`。`only` 的传递闭包在 `compiler/pipeline.py`(按模式感知的 `_implied_needs`),`to_node` 切片在 `suite/modes.py`(仅 chain 消费),执行器都已支持。
3. **逐单元台账与总状态**:现状有两个问题。
   - **总状态取错**(现有缺陷):`_fanout_graph` 每收到一条 `scenario.end` 就覆盖 `proj["status"]`,启动成功时执行状态等于**最后结束的那个单元**的状态,`exit_code` 被忽略。于是带后置 teardown 的 Suite 只要 teardown 通过就记为 passed,并行分支里先失败的一路会被后通过的一路覆盖,判定门不通过(执行器只改退出码)也被吞掉;`_bump_counters` 也按整图计 1 通过 / 1 失败。改为:总状态由 `run.finished` 的 `exit_code` 与计数(failed / error / blocked / halted)推导,计数按单元累加。
   - **只有一条图行**:现在只写一条 seq=0 的行,`unit_id` 取最后一个 `scenario.end` 事件的 `unit` 标签 —— 台账上这行可能显示任意成员的 ref,读侧无法区分图行 / 单元行。改为按物化后的单元清单逐单元写 `ExecutionRow`。对齐点:seq 分配要在 `uq_execution_row_seq (execution_id, seq)` 唯一约束下与既有行不冲突;at-most-once 恢复路径(已开跑即整图判失败)也写 seq=0 图行,改造后两条路径的行形态要一致。逐单元状态与耗时以事件的 `unit` 标签为键:已执行单元按 `scenario.start` / `scenario.end` 的 `timestamp` 配对算耗时、状态取 `scenario.end.status`;blocked / cancelled 单元不发事件,从 `run.finished.details` 里按 `unit.id` 补齐。不以 `details` 为已执行单元的耗时来源 —— 已执行单元的 details 行 `scenario_id` 填的是场景自身 id(`_detail_row`),×重复的 `ref#k` 变体之间无法区分。执行器不加第二处改动。
4. **判定门结论**:执行器 `_apply_gates` 只改退出码并追加 `__gates__` 明细,且明细里的 `halt_reason` 是拼接字符串、机器不可读,平台无从解析;由执行器发一条结构化事件(度量、阈值、实测值、是否通过),平台经现有事件通道(`_EventIngester`)落到执行记录上。这是执行器一侧唯一的改动。
5. **执行归属**:编排执行现在的 `scenario_id` 取第一个单元的场景,会算进那个场景的历史;改为写 `kind = suite_graph`、`suite_id`,`scenario_id` 写占位 `suite-<suiteId>`,`scenario_name` 写 Suite 名。
6. **改名与注入透传**:`GraphUnitSpec` 现在没有 `map` 字段,`materialize_graph` 的 `_decl` 也不输出它,连线检查器的同名改名无处生效;`GraphUnitSpec` 增加 `map`,`_decl` 显式写出(同第 2 处,手工挑键不会自动透过)。`injectionEntryIds` 已在 `GraphUnitSpec` 中,拼装时从 `mode_config` 取值填入即可。

两点补充说明。其一,`parallel` / `nRuns` 在执行器侧是嵌套形态(`parallel` = `SuiteGraph.policy.parallel`,`n_runs` = 逐单元 `policy_kwargs`),不是 SuiteGraph 顶层字段;但顶层 → 嵌套的变换 `materialize_graph` 已经在做(graph 级 nRuns 下沉到逐单元 `policy_kwargs`、parallel 进 policy),本次不需要为此新增改动。其二,`policy_kwargs` 在执行器侧是开放 dict,拼装方拼错键在 schema 层不报错、要到执行器构造期才炸 —— 收口 `POST /runs` 后平台成为唯一拼装方,拼装函数对 `control` / `policy` 相关键做白名单校验,把错键挡在下发前。

**前端模块**

- 路由:`/suites`、`/suites/new`、`/suites/:id/compose`(仅 `canEdit`,否则重定向到 `/suites/:id`)、`/suites/:id`;删除 `/suites/composer`;侧栏合并为单入口。
- 页面:`SuiteLibrary`(02)、`SuiteCompose`(10–13)、`SuiteManage`(20 / 21 两个页签,含只读态);删除 `SuiteComposer.vue`,`SuiteDetail.vue` 由 `SuiteManage` 取代。
- 组件(`components/suites/`):场景抽屉、画布(基于已在依赖中的 `@vue-flow/core`)、单元检查器(含数据行与注入条目选择)、连线检查器(含同名输入改名)、结构状态条、四种结构说明、完成编排面板、模式条、判定面板(判定门 + 横切断言表单,不再手写 JSON)、运行预检弹窗、运行记录、发布确认框(公共 Suite 加私有成员与发布共用)、只读横幅。
- 纯函数 `utils/suiteStructure.ts`:结构推断、环检测、按结构排成员顺序,单独单测。
- 执行记录页:`suite_graph` 执行显示 Suite 名并链到 21,「重跑」改为「重新运行 Suite」。
- 已有的反向入口 `AddToSuiteDialog.vue` 与场景详情「所属 Suite」保留,链接指向 `/suites/:id`;`AddToSuiteDialog` 补上公共 Suite 的发布确认分支。
- 测试适配:侧栏合并会破坏 `Sidebar.test.ts` 五处入口计数断言(展开态 `links` 16、`hrefs` 13、`nav-text` 17、`rows` 17,折叠态另有第二处 `links` 16 —— 漏改即挂);`Suites.test.ts`、`AddToSuiteDialog.test.ts`、`ScenarioDetailView.test.ts` 随路由与接口调整适配。画布参照 `views/EndpointBoard.vue`(`@vue-flow/core` 在生产使用的唯一先例,648 行)。

**命名统一**:界面与后端生成的文案一律用「Suite」。后端现存「用例组」字样需一并改:`shares.py` 的分享 / 拷贝通知、`suites.py` 的管理员下架通知、`scenarios.py` 的连带下架通知;对应测试断言同步更新。

## 运行链路

![运行链路](diagrams/run-chain.png)

图中是串联、扇出、依赖编排的链路。加粗的 run 是本次的关键改动:由服务端而不是前端拼装 graph,保证运行的就是保存的编排;validate 与 run 用同一份拼装逻辑,只是不入队。聚合不经过 graph:run 内按成员顺序逐个调用现有的 `dispatch_run`,每个成员一条独立执行,共用 batch_id,结果在批次视图里看。运行闸在 run / validate 入口统一判一次(`_require_run_async` + 逐单元 `can_run_scenario`)。

## 对系统的影响与风险

影响不大,主要在 Suite 范围内。Suite 以外只有执行记录要改:编排执行现在会算进第一个成员场景的历史,重跑也只会重跑那个场景,总状态还会被最后结束的单元覆盖,需要加归属标记、修正状态推导并调整重跑。Suite 未正式使用,不需要兼容。

| 层 | 影响 | 说明 |
| --- | --- | --- |
| 执行器 | 很小 | 只加一条判定门结论事件;其余能力已具备 |
| 数据库 | 小 | `suite_members`、`suites`、`executions` 各加列,无数据迁移 |
| 平台后端 | 中,主要在 Suite | Suite 路由重写、编排通道补六处(含总状态修正);场景删除路径加一步引用清理与 rev 推进(在 `scenario_store.delete` 内单点实现,FK CASCADE 不代劳,见约束 6);执行记录的场景维度查询与重跑按 `kind` 区分 |
| P2 已落地部分 | 小 | 拷贝分享的深拷贝补编排配置重映射;发布 / 分享拒绝草稿;新增公共 Suite 的复制入口;删除 Suite 通知引用者;运行闸、读闸、列表口径沿用不改 |
| 前端 | Suite 内大,其余很小 | 画布为新开发量;管理页多一个只读态;其余只动侧栏、路由、场景详情链接、反向入口的发布确认、执行记录页对 Suite 运行的显示与重跑 |
| 其他功能 | 很小 | 场景库、单场景运行、权限一期不动;通知有两处小改:suite_graph 执行的完成通知(走批次通知 `upsert_execution_finished`)文案与链接指向 Suite 运行而非场景名,以及「用例组」文案统一;场景的执行历史、健康趋势、工作台最近执行要排除编排执行 |

**风险与应对**

- **编排模式只跑一行数据**:用户可能以为方案里的多行都会跑。单元检查器和预检都明示所跑的那一行;需要多行的场景放在聚合 Suite 里。
- **中断恢复**:编排执行中断后不重放、整体判失败(at-most-once)。大 Suite 跑到一半 worker 重启会整体失败,需配合「只重跑失败单元」。聚合不受影响,每个成员独立恢复。
- **队列占用**:执行队列是单 worker 先进先出,一个大 Suite 会排在所有人的单场景运行前面。正式使用前评估优先级或下调总 runs 上限(现 1000)。
- **预检依赖执行器编译**:validate 要经过 plate convert 和执行器编译,任一不可用时降级为只做本地结构检查,并在状态条标明「未校验变量」。
- **画布规模**:成员上限 100,节点多时画布难读;管理页保留列表视图,画布提供自动布局和缩放。
- **被引用者运行时的认证别名**:`materialize_graph` 与单场景分发都按**发起人**解析认证别名(`_resolve_exec_auths` 按 owner 过滤)。被引用者跑他人的 Suite 时,属主私有的别名解不到,相关步骤在执行时报错 —— 与 P2 单场景引用运行同口径,本次不另做跨属主凭证。预检把解不到的别名列为警告,用户可在运行前知晓;是否开放共享别名由 P2 后续统一决定。
- **公共 Suite 的级联公开**:公共 Suite 加私有成员会连同其数据集一并公开。确认框必须列出将被公开的场景,画布拖入、管理页、反向入口三处不得绕过。

## 实施计划与验收

分四步交付,每步独立可验收;第 1 步是其余三步的前提,2 与 3 可并行。

1. **后端打底**:迁移 0014;composition 接口与 rev;引用清理(移除成员、场景删除,含 rev 推进);编排通道补齐六处(含总状态修正);`/suites/{id}/run` 按模式分流与运行闸;`/suites/{id}/runs`;执行记录按 `kind` 区分与重跑拦截;草稿上限与清理;P2 衔接(深拷贝重映射、发布 / 分享拒绝草稿、`/suites/{id}/fork`、删除通知引用者、公共不变量进 composition、能力位、列表 `shared` / `public` scope、「用例组」文案)。
   - 验收:聚合运行与现状一致;编排模式下单元按所选那一行运行;编排执行不出现在成员场景的执行历史里,对它点重跑会转去运行 Suite;删除场景后配置里不留悬空 needs / `map`、Suite 的 rev 有推进(旧 rev 的整体保存被拒,而非仅接口路径);试跑选中段只执行所选单元及其上游,串联可只跑到某一步;编排执行有逐单元台账行,且与 at-most-once 恢复路径的行形态一致;**主体单元失败而后置通过时执行判为失败,判定门不通过时执行判为失败**;`control` 透传只落 `only` / `toNode`,拼装产物里不出现 `fromNode`;`map` 透传到执行器后同名歧义消失;validate 的逐成员可运行性与 `/run/precheck` 是同一份实现;反向入口加成员后,旧版本号的整体保存被拒;他人场景加入被拒;拷贝分享与公共复制得到的副本编排结构与源一致且只引用副本场景;被引用者能运行不能保存,公共读者不能运行;草稿发布 / 分享被拒;公共 Suite 经 composition 加私有成员返回 `suite_member_publish_required`。
2. **管理页与列表**(02、20、21、30):接上真实的编排保存、运行、预检和历史;只读态与浏览范围;删除 `/suites/composer`,侧栏单入口。
   - 验收:四种模式均可在管理页配置并运行;切到聚合会先确认丢弃的连线;从聚合切到编排模式时多行方案的成员被标出;在途时预检直接给出「查看」;两处并发保存时后者收到冲突提示;被引用者 / 公共读者看到只读态且按钮符合角色表;被引用者可从只读态「转为副本」得到可编辑副本;公共 Suite 加私有成员弹发布确认;被引用者在 21 只看到自己的运行;侧栏单入口与路由合并后,受影响的现有测试(侧栏五处入口计数等)同步更新且全绿。
3. **预检、校验与重跑**:`/suites/{id}/validate` 接执行器编译;连线上的变量、悬空引用与同名改名;执行器发判定门结论事件;只重跑失败单元。
   - 验收:成环、输入无上游供给、输入歧义三类问题在运行前报出,并定位到节点或连线;不可运行单元与解不到的认证别名在预检中列出;21 显示判定门实测值;只重跑失败单元时,通过的单元中只有失败单元的上游会重跑。
4. **新建画布**(10–13):拖入、连线、结构推断、草稿、完成编排、四种结构说明。画布本体只做最小闭环(拖入、连线、环拒绝、状态条),右侧检查器、模式条、判定面板复用第 2 步管理页的组件,压开发量;参照 `EndpointBoard.vue`。
   - 验收:`suiteStructure.ts` 覆盖五条识别规则、环检测和按结构排序;首次拖入即出现草稿;直线自动识别为串联;保存后在管理页看到同一结构与顺序;非属主访问画布路由被重定向到只读管理页。

## 决策记录

全部事项已定,开工不再有阻塞。

- [x] **运行通道**:聚合保留批次通道,串联 / 扇出 / 依赖编排走编排通道且每个单元只跑一行数据(见「概念模型」约束 5)。
- [x] **串联与依赖编排的执行语义**:已核实无差异。执行器把串联编译成按顺序的线性依赖,传值在所有模式下都按全部上游自动连线;直线一律识别为串联,不再让用户选择(见约束 4)。
- [x] **试跑选中段与只重跑失败单元**:已核实执行器支持。`Control.only` 执行所选单元及其传递上游,三种编排模式通用(聚合只需发起所选成员);`from_node` 切片不开放。
- [x] **前置 / 后置作为成员**:采纳,`suite_members` 加 `role` 列,属主约束自动覆盖。
- [x] **管理页「在画布中改结构」**:保留,作为大改结构的出口,保存后回到管理页。
- [x] **对外命名**:统一叫「Suite」。侧栏、页面标题、反向入口弹窗、场景详情、后端通知文案一律用「Suite」,不再出现「用例组」。
- [x] **草稿**:不计入每人 50 个上限;30 天未改动且没有主体成员的草稿,由后台清理任务删除 —— 实现为后端 lifespan 轻量循环任务、小时级巡检(平台无周期任务基建,不为此新引调度框架)。草稿不可发布、不可分享。
- [x] **队列与总 runs 上限**:本次不改执行队列,保留 `SUITE_RUN_TOTAL_CAP = 1000`;正式使用前按真实运行数据复核,列为上线检查项。
- [x] **与 P2 的关系**:P2 后端已落地,本方案沿用其读闸、运行闸、列表口径与发布联动,只补编排配置相关的衔接(深拷贝重映射、公共不变量进 composition、草稿排除、公共复制入口、只读态);graph 授权闸已在 P2 换为 `can_run_scenario`,无需再改。
- [x] **编排运行的不可运行单元**:整体拒绝并在预检中列出,不做单元级跳过(图的依赖与传值不允许缺口);聚合保持跳过。
- [x] **被引用者的认证别名**:按发起人解析,与 P2 单场景引用运行同口径;预检告警,本次不做跨属主凭证。
- [x] **运行记录可见性**:属主 / 管理员看全部发起人,被引用者只看自己发起的。

## 附录:离线查看可交互原型

`prototype-src/` 是原型画板源文件和一个极简离线渲染器 `viewer.html`(只实现画板用到的模板子集,用于查看,不是生产代码)。

```bash
cd prototype-src
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000/viewer.html?board=Main.dc.html
```

- 画板间链接可点击跳转。
- 12 搭建过程:`viewer.html?board=Compose.dc.html`,顶部「上一步 / 下一步」切换四步。
- 20 管理页:`viewer.html?board=Workspace.dc.html`,模式条可切换四种模式。
- 指定初始状态:`&props={"startStep":1}`(12)或 `&props={"startMode":"chain"}`(20)。

在线版本:[Suite 整合设计稿(画布)](https://claude.ai/artifact/Kggdk5yNCfGtNDhcvK5Yq1)、[Suite 层重构设计方案(文档)](https://claude.ai/artifact/XVe6pwx5Nfa1zK1wnfypBq)。两者为评审前版本,P2 补充与本版修正以本文为准。

## 修订记录

本版相对评审稿(基线由 `6bd98fa` 更新到 `643a14b`)的改动:

**修正**

- 约束 6 / 并发编辑 / 影响表:用户处置三条路径不需要清理引用或推进 rev(publicize / purge 整体删除 Suite,transfer 整体改属主,引用始终有效);需要清理的只有移除成员与场景删除两条,场景删除在 `scenario_store.delete` 内单点实现。
- `mode_config.row` 键名 `dataSetId` → `datasetId`,与平台权威键一致。
- 编排通道第 3 处:逐单元耗时改为按 `unit` 标签配对 `scenario.start` / `scenario.end` 时间戳;`run.finished.details` 只用于补齐 blocked / cancelled 单元(已执行单元的 details 行以场景 id 为键,无法区分 ×重复变体)。
- `Sidebar.test.ts` 入口计数断言为五处,不是三处(展开态 `links` / `hrefs` / `nav-text` / `rows` 四种,折叠态另有第二处 `links`);`EndpointBoard.vue` 位于 `views/`,648 行。

**补充(两版都遗漏)**

- 编排通道第 3 处新增「总状态取错」:现状按最后一个 `scenario.end` 定执行状态,后置通过即判通过、判定门失败被吞;改由 `run.finished` 推导,计数按单元累加。验收补对应用例。
- 新增编排通道第 6 处:`map` 透传(`GraphUnitSpec` 与 `_decl` 均缺),`mode_config` 补 `map` 与 `injectionEntryIds`。
- 编排执行 `scenario_id` 写占位 `suite-<suiteId>`(列为 NOT NULL)。
- 409 `suite_run_in_progress` 链接参数 `batchId=` 修正为 `batch_id=`。

**基于 P2 落地的补充**

- 范围、决策记录:删除「P2 不在本次范围」与「P2 时再换 graph 授权闸」(已换为 `can_run_scenario`);新增「与 P2 的关系」等四条决策。
- 概念模型:新增「访问角色」表与能力位;新增约束 8(拷贝分享时编排配置重映射)。
- 页面:02 浏览范围与归属列;20 只读态、发布 / 分享入口位、公共读者「复制到我的」;21 按角色的可见性;30 不可运行单元整体拒绝、认证别名告警;12 非属主重定向。
- 交互规则:新增「P2 权限、分享与发布」一节(只读态、运行、公共成员约束、发布、分享、删除、运行记录可见性)。
- 接口:composition 套用公共不变量;发布 / 分享拒绝草稿;新增 `POST /suites/{id}/fork`;拷贝分享补重映射与草稿排除;删除 Suite 通知引用者;run / validate / runs / rerun-failed 写明权限口径。
- 命名统一扩展到后端通知文案(`shares.py`、`suites.py`、`scenarios.py`)。
- 风险:替换原 P2 衔接风险为「被引用者的认证别名」与「公共 Suite 的级联公开」。

**第二轮评审修正**

- 列表 `scope` 补 `shared` / `public` 两档(02 的三档浏览范围需要;服务端分页下客户端过滤不可行),进 API 表与第 1 步 P2 衔接清单。
- 被引用者只读态补「转为副本」:复用现有 `POST /shares/{id}/fork`(suite 引用已支持,零后端改动),进 20 / 只读态规则与第 2 步验收。
- `Sidebar.test.ts` 计数断言由四处修正为五处(折叠态测试另有第二处 `links` 16,漏改即挂)。
- 数据模型补 suite_graph 执行的快照口径:不存首单元场景(否则详情页快照抽屉展示误导性单场景快照),改存 graph 拼装产物或 Suite 摘要,快照端点读侧按 `kind` 区分。
- 21 与「运行记录可见性」补公共读者口径:无发起记录,runs 页签隐藏或空态提示「复制到我的后可运行」。
