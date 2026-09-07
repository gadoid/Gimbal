# 动态取数源设计 — QueryView 端点注记 + 组合期取数解释器

> 状态:设计定稿待评审(2026-09-07 brainstorming 逐节过审:模型/消费模式/流程/缓存/凭证/配方落点;配方落点采用户提议的**端点注记式**,独立 recipes.py 方案作废)
> 日期:2026-09-07
> 前置:2026-09-05 field-state-catalog(§1.4 一致化:字段的每个决策都是字段属性);2026-09-07 找回/穿线已实施(65740b4c)
> 分支:`feat/field-state-catalog`

---

## 0. 背景与问题

### 0.1 配置器与动态内容的张力

平台的主业是**配置器**:产出自含、确定、可重放的场景资产。但被测系统存在大量
动态获取的内容——某字段的选项由另一接口查询得到(费用名称 ←
`/api/home/cost/amountCostList` 的 `cost_name`,业务持续增补的 130+ 字典)、
某字段的合法值依赖业务流当前状态(委托单号 ← 待委托订单列表)。两条出路:

| 方案 | 做法 | 代价 |
|---|---|---|
| 方案一:编排进过程 | 把查询接口也编排进场景步骤,extract + `${var}` 穿线 | 业务流程复杂度上升(每个取数都多步骤) |
| 方案二:平台动态取数 | 平台直接向被测系统查询,渲染回配置面 | 平台整体复杂度上升 |

### 0.2 假二叉分解

动态需求不是一块,按**值的腐烂性**分两形:

- **A 选项字典**:字段候选来自字典接口(费用名称、币种、港口)。组合期认知问题
  ——作者需要"看见可选项";字典值本身长期稳定,钉下不腐;
- **B 存在性依赖**:字段合法值依赖业务流时点(待委托订单、可用容器)。数据时点
  问题——钉下的值随业务推进腐烂(订单被派、状态跃迁)。

B 内部再分两种消费:**现钉**(组合期查+选,值以字面量落配置,接受腐烂风险)与
**活查**(配置期生成真实查询步骤,运行时重查,值永不过期)。

### 0.3 机制空间五格与尺轨原则

| # | 机制 | 值何时定 | 现状 |
|---|---|---|---|
| 1 | 静态 enum(plate 目录) | 目录发版 | 已有(渲染通道有缺陷,§7.1 顺车修) |
| 2 | carry 值表 | 物化时注入 | 已有 |
| 3 | 场景查询步骤(extract + `${var}`)= 方案一机制 | 运行时 | 已有 |
| 4 | **组合期取数(本设计)** | 作者配置时 | 新增 |
| 5 | 运行时符号解析(引擎隐式查询) | 运行时 | **禁止** |

**尺轨原则**:配置器产物必须自含/确定/可重放。**FETCH 合法**(查询服务作者,
选择后值显式钉进配置);**RESOLUTION 非法**(执行引擎运行中隐式向被测系统查值
——产物不再自含,重放依赖外部时点)。本设计 = 方案二之形(平台取数)服务作者,
方案一之机制(查询步骤)经 B-活查按需支付——二叉就此消解。

### 0.4 需求追溯表(讨论要义 → 设计落点)

| 用户关切(原话要义) | 落点 | 章节 |
|---|---|---|
| 方案一加业务流复杂度,方案二加平台复杂度 | 尺轨消解:组合期 FETCH + 活查复用方案一 | §0.3 / §8 |
| 字段定义还在 plate,但要与接口绑定 | value_source 字段属性(一致化延续) | §3.2 |
| 多字段从同一接口查询,查完还要处理再渲染 | QueryView(items/label)+ 封闭词表 + 行扇出 | §3.1 / §4.2 / §7.3 |
| 有了接口也要有组装过程,取回的结果要做处理 | T0-T5 流程 / 组装机械 + 处理封闭 | §4.1 / §4.2 |
| 每次都是查完注入字段再让用户选? | 先渲染候选 → 用户选 → 写字面量;非注入 | §7.5 |
| 选某字段时其他相关字段一并填入 | 一查多填行扇出 | §7.3 |
| 单个的还是单个查询写值 | N=1 退化为单字段下拉 | §7.2 |
| 缓存如何实现,对内存的影响 | TtlLruCache 实现级设计 + 上界测算 | §5 |
| 用哪个用户去查询 | 专用查询凭证(服务绑定托管) | §6.1 |
| 同一用户单 session 无法并发 | 并发请求 ≠ 并发 session;凭证独立 + 三层并发 | §6.2 / §6.3 |
| 配方改为跟普通接口定义一样的模式? | **采纳**:QueryView 挂端点注记,零重复声明 | §3.1 |

---

## 1. 目标与非目标

**目标**

1. **组合期取数**:字段候选/实体值可在配置时实时查询被测系统,选择后以字面量
   落配置(产物自含不破,尺轨 §0.3);
2. **一查多填**:多字段共享同一视图,一次选择行扇出写值;
3. **机制最小**:plate 只加注记不加体系(端点 + 视图,无平行配方层);平台侧
   一条通用解释器路由 + 零格处理词表;
4. **执行核零改动**:gimbal resolver/jsonpath/context 不碰(与 09-05 同纪律)。

**非目标**

- 运行时动态解析(尺轨禁止,永不做);
- 查询处理 DSL(词表封闭,§4.3);
- B-活查实施(二期;本稿 §8 只锁形状);
- 响应面/断言面任何变化;
- 场景存储/导出链任何变化(v1 钉值走既有 body 写入通路,导出无感)。

---

## 2. 总裁决:都做、现钉先行、活查二期

- **A 与 B 都是真需求**,不裁掉任何一个;
- **B 现钉先行**:内网数据流速可控,腐烂是低频事件;现钉零新增机制(与 A 同一
  条"查→选→写字面量"通路)覆盖绝大多数场景;
- **活查二期**:步骤物化 + 变量穿线的复杂度,只付给真正腐烂敏感的绑定;机制上
  复用方案一的既有查询步骤,零新概念。

---

## 3. plate 目录模型

### 3.1 QueryView(端点注记式配方 — 用户提议采纳)

查询接口**本身就是被测系统接口**,一半已在目录里(order_entrust_order_page、
audit_audit_page、order_order_detail 均在 18 端点中)。配方不另立体系,是
**普通端点定义上的取数视图注记**——method/path/请求缺省全部复用端点声明,
单一真源,端点改路径取数自动跟随:

```python
class QueryView(BaseModel):
    """端点作为取数配方时的行集视图(本设计 §3)。

    配方 = 端点声明(单一真源)+ 本注记。params 是声明缺省
    (default ▸ example 链)之上的固定过滤预设(如 entrust_status=1
    的"待委托"视图);items/label 定义响应行集的提取与呈现。
    词表封闭(§4.3):v1 仅 items 提取 + label 列,无 transforms 键。
    """
    name: str                              # 全局唯一(跨端点);四重身份见 §3.5
    params: dict[str, Any] | None = None   # GET→querystring / POST→JSON body
    items: str                             # 响应行集 JSONPath,如 '$.data.list[*]'
    label: str                             # 选择器显示列(行内键)
```

```python
# EndpointSpec 顶层增(extra="forbid" 下显式声明):
query_views: list[QueryView] | None = None
```

**既有端点升级**(加 3 行,其余零重复):

```python
# systems/fin/endpoint/order_entrust_order_page.py(既有文件)
ORDER_ENTRUST_ORDER_PAGE: Final[EndpointSpec] = EndpointSpec(
    ...,
    query_views=[QueryView(name='pending_orders',
                           params={'entrust_status': '1'},
                           items='$.data.list[*]', label='order_no')],
)
```

**字典端点照常接入**(amountCostList 不在 18 内 → 新建端点文件,普通模式;
字典接口成为目录公民 = 获得声明、golden 覆盖、自身可测——与
gimbal-query-field-verify 技能同构收敛):

```python
# systems/fin/endpoint/cost_amount_list.py(新端点)
COST_AMOUNT_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.cost.amount_list', ..., method='GET',
    path='/api/home/cost/amountCostList',
    query_views=[QueryView(name='cost_list', items='$.data[*]', label='cost_name')],
)
```

**多视图**:同一端点不同 params 预设 = 多个 QueryView(待委托/全部),不用多端点。

### 3.2 DeclarationEntry.value_source(字段绑定)

```python
class ValueSource(BaseModel):
    view: str         # QueryView.name(全局唯一引用)
    column: str = ""  # 行内取值列;空 = label 列(N=1 退化:显示列即值列)

# DeclarationEntry 增:
value_source: ValueSource | None = None
```

字段定义仍在 plate(用户裁定);绑定是字段属性 —— 09-05 §1.4 一致化的延续。
N=1(单字段下拉)与 N>1(一查多填)不是两种机制,是**同一绑定的分组结果**:
前端按 `value_source.view` 分组,N>1 组共享一个行集选择器(§7.3)。

### 3.3 校验

| 层 | 规则 |
|---|---|
| 单模型 | QueryView 形状:name 非空 ASCII 标识符 / items 以 `$.` 开头 / label 非空 |
| 聚合层(fin ALL_ENDPOINTS + plate 策略测试) | ① **view name 全局唯一**(跨端点查重,构造期拒);② **引用闭合**:`value_source.view` 必命中某端点的某视图;③ **enum × value_source 互斥**(enum 是静态闭集,value_source 是动态开集,并置 = 定义精神分裂) |
| 运行时 fail-soft | column/label 不做构造期校验(需活响应):列缺失 → 选择器行显示原始 JSON 兜底,不炸 |

### 3.4 wire 与索引

- **/full 投影**:端点带 `query_views`、条目带 `value_source` → golden
  (io_declarations fixtures)**意识性重钉**(变化面:含视图的端点 + §7.1 的
  enum 回填 3 字段,同批重钉);
- **plate 新只读聚合路由 `GET /api/query-views`**:
  `[{name, endpoint_id, system, service, method, path, params(合并后), items, label}]`
  —— 纯投影零状态,遍历端点目录聚合;platform 经 plate_client 既有
  memo + 熔断模式取用,不重复发明;
- **dispatch 基线零重钉**:v1 不改任何场景语义(钉值走既有 body 通路,导出链无感)。

### 3.5 命名不可变纪律

view name 一经使用**不可改名**(与 endpoint id 同款纪律),四重身份:
① 解释器路由键;② `value_source.view` 跨端点引用;③ 缓存键;④ 二期活查
`${var.<view>…}` 变量名(场景兼容资产)。golden 守护。

### 3.6 与 09-05 的关系(source_kind 休眠词表)

`source_kind` 的 `lookup` 休眠词 v1 **不动**:其注释语义是"只读展示
(`${var.xxx}`)",与取数选择器的可写形态不合;`value_source` 存在本身即信号。
二期活查落地时再议是否派生 lookup 语义(挂账 §12.6)。

---

## 4. 平台解释器路由(一条通用路由解释所有视图)

OpenAPI operation ↔ 通用 HTTP 客户端的同构:视图是数据,解释器是唯一的执行者
——新增视图零平台代码。

### 4.1 路由与流程(T0-T5)

`GET /api/query-views/{name}/rows?refresh=0|1`(platform backend,新
`routers/query_views.py` + `services/query_view_runner.py`;CurrentUser 鉴权
——查询身份是**平台服务绑定的查询凭证**,不是平台用户自己的)。

```
T0 打开目录   composer 拉 /full(条目携带 value_source);
              platform 经 plate 索引 memo 视图注册表(冷启动一次)
T1 分组       前端按 value_source.view 分组绑定字段(N=1 / N>1 组)
T2 触发       用户点绑定字段「查」钮 → GET /api/query-views/{name}/rows
T3 解释执行   索引定位端点 → L1 缓存 → L2 同视图单飞 → L3 凭证闸
              → 组装请求(§4.2)→ resolve_service_url + 查询凭证 token → 发送
T4 处理       jsonpath(items) 提取行集 → ≤MAX_ROWS 截断(标记 truncated)
              → 回传 {view, rows, truncated, fetched_at, cached}
T5 落值       前端渲染选择器(label 列 + 绑定列);用户选 → setValue 写字面量
```

### 4.2 组装(机械)与处理(封闭)

**组装,零自由发挥**:

1. 索引定位 view → 端点声明(method/path/请求声明缺省);
2. params 合成:`view.params` ▸ 声明 `default` ▸ 声明 `example`;合并后必填键
   仍缺 → **422 视图定义错误**(fail loud,修视图定义,不静默补 None);
3. 服务 URL 解析复用执行链服务绑定;凭证 = AuthSession 托管的查询凭证(§6.1);
4. 按 ApiSpec 组装(GET → querystring;POST → JSON body)发送;超时 10s、
   **不重试**(查询尽力而为,失败即降级态)。

**处理,v1 词表零格**:

- 仅 `jsonpath(items)` 提取行集 + 行数截断;**返回整行 dict 不投影** —— 列绑定
  在字段侧,任何列可用,免重查免预定义列清单;
- **不设 transforms 键**(YAGNI):未来准入候选仅 filter/first/dedupe 三格,
  且需重新评审;若准入自由文本检索,检索词**不进缓存键**(不缓存,防键爆炸)。

### 4.3 DSL 红线

测试平台腐化于查询处理 DSL 的蔓生——每个"查完再处理一下"都是一格词表。词表外
诉求 = **显式场景步骤**(方案一机制收容,§8 活查即其出口),不是解释器新词。
这条红线是本设计能否长期存活的判据。

---

## 5. 缓存(实现级)

### 5.1 形态与界限

进程内 `TtlLruCache`(OrderedDict),~40 行:

| 参数 | 值 | 依据 |
|---|---|---|
| `QUERY_CACHE_TTL` | 300s | 字典/列表变更频率远低于此;选择语义 = 快照非实时 |
| `MAX_ENTRIES` | 64 | 视图实际个位数,64 是宽上界 |
| `MAX_ROWS` | 200 | 费用字典 130+;截断需 truncated 标记透出 |

- **惰性过期**:读时判 TTL,过期即 miss 重取;无后台线程;
- **LRU 容量逐出**:命中 `move_to_end`,溢出 `popitem(last=False)`;
- **错误永不缓存**(失败让下次重试);**空结果缓存**(空字典也是有效答案);
- **refresh=1 旁路**:绕过读,强取后写回覆盖(选择器的"刷新"钮);
- **键 = view name**:view 的 params 是视图身份的一部分(固定预设),键天然
  完整;未来若准入检索词,该词不进键(§4.2)。

### 5.2 并发三层 + 锁序

| 层 | 机制 | 效果 |
|---|---|---|
| L1 TTL 缓存 | 命中直接回(cached=true) | 大多数请求零上游 |
| L2 同视图单飞 | `dict[view, Lock]` | 同视图并发合一发,其余等共享结果 |
| L3 凭证闸 | `dict[credential, Lock]` | 同凭证**最多 1 个在途 SUT 请求**(跨视图串行) |

锁序:**view 锁外层 → 凭证闸内层;永不同时持两把 view 锁** → 无死锁。合计
~10 行。

### 5.3 内存上界

64 视图 × 200 行 × 1-2KB/行(整行 dict)≈ **13-26MB 理论上限**,实际远低
(视图个位数、行多为窄字典)。有界即可接受。**不引 Redis**:multi-worker
各自进程内缓存,最坏 N× 冷启动放大,内网单体可受(边界表 §9)。

---

## 6. 凭证与单会话约束

### 6.1 专用查询凭证

每个服务绑定托管**一个查询账号**(AuthSession 管 token;服务绑定配置扩
`query_user` 键指向该账号,缺省回落绑定的主凭证)。查询凭证是**平台配置**,
与平台登录用户无关、与场景执行配置无关。

### 6.2 三规则(单会话约束下的设计)

被测系统**同一账号同一时间只能存在一个 session**——限制的是并发 session 数,
不是单 session 内的并发 HTTP 请求数:

1. **解释器绝不自动重登录**:token 过期/401 → 降级态 + "到认证页手动刷新"提示
   (自动重登录会踢掉活跃 session,含正在执行的场景);
2. **查询凭证永不进场景执行配置**:反向防碰撞——执行 dispatch 不会挤掉查询
   session,反之亦然;配置页发现挪用作告警(挂账 §12.3);
3. **并发三层**(§5.2):单 session 内请求可并发,凭证闸兜底串行化。

### 6.3 已知凭证边界

- **权限腐烂**:查询凭证(常偏高权限)可见的候选 ≠ 执行账号可用的值。处置:
  查询凭证选**最小权限账号**;运行期失败由断言暴露;不试图静态预测;
- **跨环境**:组合期查询走服务绑定默认环境,场景执行可换 env → 钉的字面量
  可能来自另一环境。v1 接受(内网单环境为主),env 联动挂账(§12.4)。

---

## 7. 前端消费

### 7.1 静态 enum 通道修复(顺车票 A)

- **根因**:FieldForm.vue L574 主面条件 `ui_kind === 'select' && item.f.enum`,
  而 text/unknown 分支(L444)在前先命中——全仓唯一 enum(audit sort_order)
  ui_kind='text',select 分支**从未触发**。是渲染通道缺陷,不是渲染器能力缺失;
- **修复**:select 分支条件改 `item.f.enum`(enum 非空即 select)且**上移到
  text/unknown 之前**;折叠区 L775 同款(`r.f.enum && !isTpl(...)`);
- **事实枚举回填**:active_tab / action / sort_order 三字段补 enum;
- **number 陷阱钉住**:select 写值现走 `String(opt)`(L589/L592),number 型
  enum 会写成 `"1"` —— entry.type 数值族时写值 `Number()` 包裹,测试钉死;
- golden 重钉与 §3.4 同批。

### 7.2 N=1:单字段下拉

绑定字段渲染「查」钮 → 选择器列 label 值 → 选 → `setValue(row[column||label])`。
例:费用名称 ← cost_list.cost_name。

### 7.3 N>1:一查多填(行扇出)

Canvas 按 `value_source.view` 分组;组内任一字段打开的选择器显示同一行集
(行 = label 列 + 全部绑定列,path 徽标区分);选中行 → **组内每字段
`setValue(row[column])`**(既有 body 写入通路 + D8 剪枝,零新写值机制)。
例:选一条待委托订单 → bl_no/客户/容器等绑定字段全落。

### 7.4 B-现钉 = 同一机制

与 A / 一查多填共用"查→选→写字面量",**无独立代码路径**;区别仅语义记账
(存在性依赖的值会腐烂,边界表 §9,逃生门 = 活查 §8)。

### 7.5 值语义:非注入

**"注入"在本仓指 carry_injection(运行时自动物化)——本功能永不注入。**
流程恒为:渲染候选 → 用户显式选择 → 写字面量;保存即所见,产物自含。
选择落值后行内显小徽标「view:<name>」(title 带 fetched_at),服务腐烂排查;
纯 UI 态,零新增存储。降级态(视图 404 / 凭证过期 / SUT 不可达)= 选择器
错误条 + 认证页引导,**绝不自动重登录**。

---

## 8. B-活查(二期,本稿锁形状)

- **一键物化**:当前步骤前插入查询 step(api = 端点声明直引,**零翻译**;
  body = 合并 params)+ extract 策略(表达式 = 行定位 JSONPath,var 名 = view name);
- **穿线**:绑定字段值改写 `${var.<view>.<column>}` —— gimbal resolver `${}`
  整体类型保持 + JSONPath 子导航已验证(09-05 §4 机制依赖注),**执行核零改动**;
- **行定位策略**(二期讨论点):首行 `$.data.list[0]` vs 过滤定位
  `[?(@.entrust_status==1)]` —— 挂账 §12.1;
- **rot 语义**:活查 = 每次执行重查,存在性依赖的值永不过期;代价 = 业务流
  多一步(方案一复杂度按需支付,只付给腐烂敏感处)。

---

## 9. 边界与风险表

| 边界 | 语义 | 处置 |
|---|---|---|
| 权限腐烂(查询凭证≠执行凭证) | 高权限查询账号的候选,执行账号未必可用 | 最小权限查询账号;断言暴露;不静态预测(§6.3) |
| 字典腐烂(现钉) | 钉下的字面量随业务推进失效 | 来源徽标 + 活查逃生门;v1 接受(内网数据流速可控) |
| 缓存过期驻留 | TTL 内业务已变(翻页/状态跃迁) | fetched_at 透出 + refresh=1;快照语义明示 |
| 跨环境 | 组合期查询走默认环境,执行可换 env | v1 接受;env 联动挂账(§12.4) |
| multi-worker | 进程内缓存每 worker 一份,冷启动 N× 放大 | 有界(§5.3);不引 Redis |
| 单会话 | 查询账号被挪用执行配置 → 约束被破坏 | 三规则(§6.2)+ 配置页告警挂账 |
| MAX_ROWS 截断 | >200 行只见前 200 | truncated 透出;超长列表本该用检索(词表准入重议) |
| 词表蔓生 | "再处理一下"逐格腐蚀解释器 | DSL 红线(§4.3),准入需重评审 |

---

## 10. 测试矩阵

| # | 层 | 用例 |
|---|---|---|
| ① | plate 模型 | QueryView 形状校验;聚合层:view name 全局唯一 / value_source 引用闭合 / enum×value_source 互斥 |
| ② | plate wire | /full 携带 query_views + value_source;/api/query-views 聚合完整性;golden 意识性重钉 |
| ③ | platform 组装 | GET/POST 分流;params 合成链(view▸default▸example);缺必填 422;服务解析 + token 注入 |
| ④ | platform 缓存 | TTL 惰性过期 / LRU 逐出 / MAX_ROWS 截断 / 错误不缓存 / 空结果缓存 / refresh 旁路 |
| ⑤ | platform 并发 | 同视图并发单飞(1 上游请求);同凭证跨视图串行;锁序无死锁冒烟 |
| ⑥ | platform 凭证 | 401 → 降级提示不重登录;CurrentUser 鉴权门 |
| ⑦ | 前端 | enum 分支优先级(ui_kind=text + enum → select);折叠区同款;number enum 写值类型;选择器行渲染 + 行扇出写值;N=1 单写;降级态 |
| ⑧ | 回归 | 三套件 + vue-tsc 0;dispatch 基线零漂 |

---

## 11. 验收清单

- [ ] 费用名称字段:打开选择器 → 130+ 费用字典全列 → 选择 → 字面量落 body;
- [ ] 待委托订单一查多填:选一行 → bl_no/客户/容器等绑定字段全落;
- [ ] 静态 enum 字段(active_tab/action/sort_order)渲染为 select;number 型
      enum 写值为 number 非 "1";
- [ ] /full golden 重钉入库;dispatch 基线零漂;
- [ ] 查询凭证过期 → 选择器提示 + 认证页引导,无自动重登录;
- [ ] 同视图连点 → 上游一次请求;refresh=1 → 重取新时间戳;
- [ ] 三套件 + vue-tsc 0 全绿。

---

## 12. 挂账

| # | 挂账 | 触发器/时机 |
|---|---|---|
| 1 | **B-活查物化**(二期主体;行定位:首行 vs 过滤定位待议) | 现钉腐烂痛点真实出现时 |
| 2 | 词表准入候选(filter/first/dedupe) | 真实诉求 + 重评审;默认拒(§4.3 红线) |
| 3 | 查询凭证管理 UI(服务绑定配置面 + 挪用执行配置告警) | 随本设计实施顺带最小配置;告警 UI 可滞后 |
| 4 | env 联动查询(组合期查询随场景 env 切换) | 多环境成为现实约束时 |
| 5 | 装饰词表联动(选择器显示列语境 label;09-05 §10.4) | 装饰词表认领时一并 |
| 6 | source_kind 'lookup' 派生语义 | 活查落地时定(§3.6) |
