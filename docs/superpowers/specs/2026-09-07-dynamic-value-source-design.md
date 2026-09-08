# 动态取数源设计 — QueryView 端点注记 + 组合期取数解释器

> 状态:设计定稿待评审(2026-09-07 brainstorming 逐节过审:模型/消费模式/流程/缓存/凭证/配方落点;配方落点采用户提议的**端点注记式**,独立 recipes.py 方案作废)
> 修订:2026-09-07 评审加固一轮(形状漂移与空结果分离 / stale-while-error / 短熔断 / query_safe 写副作用护栏 / 投影列集 / 缺列跳过——后两者推翻初稿"整行返回不投影"方案)
> 修订 2:2026-09-08 评审收尾(示例 query_safe 自洽勘误 / 视图参数闭合构造期检查 / params 键语义 / 超时鉴权跟随 ApiSpec;新增:能力定位 §0.3——值域校验前移 + L1-L3 谱系 + 两线接口 = 产物;绑定 = 共识→发版 §3.6;边界三行 §9——双通道投影窗 / 钉值来源不持久化 / 查询端点双重角色)
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

**能力定位**(2026-09-08 评审补):本设计是**值域校验前移**,不是"接口测试
前移"——无效值类错误(费用名不存在/订单号失效/枚举写错)的发现机制,从
"执行期 400 反馈回路"前移为"配置期可见可选";机制是**可见化而非门禁**
(手打错值照样存:管"选得对",不管"写得对"——写得对归执行期断言)。每次
取数顺带演习目录声明(method/path/params 走真实请求),声明漂移在配置期降级
显形。放进能力谱系:字段始终是控制点、目录始终是政策源——L1 状态自动化
(09-05 field_states)→ **L2 值域自动化(本设计,value_source)** → L3 值解析
自动化(活查,§8,按需回到执行期)。配置线与执行线的**唯一接口是场景产物**
(钉下的字面量):执行器对查询发生与否无感知,解释器可整体移除而不影响任何
已存场景;两线共享的只有平台地基(服务解析 / AuthSession),不共享调度/重试/
证据——两线失败哲学相反(执行 fail-loud 重试留痕,查询 fail-soft 降级不断炊),
强并即打架。

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

**既有端点升级**(注记数行,其余零重复):

```python
# systems/fin/endpoint/order_entrust_order_page.py(既有文件;api: POST
# /api/order/orderEntrust/orderPage, auth=bearer, timeout_seconds=30)
ORDER_ENTRUST_ORDER_PAGE: Final[EndpointSpec] = EndpointSpec(
    ...,
    # §3.3④:非 GET 端点挂视图须显式声明写副作用白名单
    metadata=EndpointMetadata(query_safe=True),
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
| 聚合层(fin ALL_ENDPOINTS + plate 策略测试) | ① **view name 全局唯一**(跨端点查重,构造期拒);② **引用闭合**:`value_source.view` 必命中某端点的某视图;③ **enum × value_source 互斥**(enum 是静态闭集,value_source 是动态开集,并置 = 定义精神分裂);④ **写副作用护栏**:非 GET 端点挂 query_views 必须显式 `EndpointMetadata.query_safe = true`(声明式白名单——fin 是 POST 重镇,不能走 GET-only 禁令;git 评审可见),违反构造期拒;⑤ **视图参数闭合**:必填键经 `view.params ▸ 声明 default ▸ 声明 example` 合并后仍缺 → 构造期拒;**"缺" = default 与 example 双 None**(空串/0/false 是合法值,不算缺) |
| 运行时 fail-soft | column/label 不做构造期校验(需活响应):列缺失 → 选择器行显示原始 JSON 兜底,不炸 |

### 3.4 wire 与索引

- **/full 投影**:端点带 `query_views`、条目带 `value_source` → golden
  (io_declarations fixtures)**意识性重钉**(变化面:含视图的端点 + §7.1 的
  enum 回填 3 字段,同批重钉);
- **plate 新只读聚合路由 `GET /api/query-views`**:
  `[{name, endpoint_id, system, service, method, path, params(合并后), items, label, columns(派生绑定列集), query_safe}]`
  —— 纯投影零状态,遍历端点目录聚合;platform 经 plate_client 既有
  memo + 熔断模式取用,不重复发明;**聚合投影纳入 golden**(合并后 params +
  columns 钉死——端点声明缺省的暗变在 re-baseline 时显形,§9);
- **dispatch 基线零重钉**:v1 不改任何场景语义(钉值走既有 body 通路,导出链无感)。

### 3.5 命名不可变纪律

view name 一经使用**不可改名**(与 endpoint id 同款纪律),四重身份:
① 解释器路由键;② `value_source.view` 跨端点引用;③ 缓存键;④ 二期活查
`${var.<view>…}` 变量名(场景兼容资产)。golden 守护。

### 3.6 与 09-05 的关系(source_kind 休眠词表)

`source_kind` 的 `lookup` 休眠词 v1 **不动**:其注释语义是"只读展示
(`${var.xxx}`)",与取数选择器的可写形态不合;`value_source` 存在本身即信号。
二期活查落地时再议是否派生 lookup 语义(挂账 §12.6)。

**绑定是共识 → 发版**:新增字段绑定(value_source)或新增视图都是 plate 发版 +
golden 重钉——动态的是**值**,不是**绑定**(绑定是低频共识,09-05 §1.2 两级
分层的忠实延续;若绑定高频化是目录治理问题,不是本机制问题)。语境级覆写
(某场景换字典)走装饰缝挂账(#5)延伸,不另开门。

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
              → 投影列集(§4.2)→ 回传 {view, rows, truncated, fetched_at, cached|stale}
T5 落值       前端渲染选择器(label 列 + 绑定列);用户选 → setValue 写字面量
```

### 4.2 组装(机械)与处理(封闭)

**组装,零自由发挥**:

1. 索引定位 view → 端点声明(method/path/请求声明缺省);**写副作用护栏复核**:
   非 GET 端点须索引携带 `query_safe=true`(§3.3④),违反 → **422**(纵深
   防御,不单靠评审);
2. params 合成(**per-key**):`view.params` ▸ 声明 `default` ▸ 声明 `example`;
   view.params **覆盖**已声明键、**追加**未声明键(如 entrust_status 未声明则
   追加;合并后 params 进索引投影 + golden,声明缺省的暗变在 re-baseline 显形);
   可选键缺省不携带;必填键仍缺 → **422**(§3.3⑤ 构造期检查为主,此处纵深
   防御;不静默补 None);
3. 服务 URL 解析复用**平台**服务绑定(公共设施,非执行链私产——两线共享地基,
   §0.3);凭证 = AuthSession 托管的查询凭证(§6.1);
4. 按 ApiSpec 组装(GET → querystring;POST → JSON body)发送;**超时与鉴权
   方案跟随 ApiSpec**(timeout_seconds / auth,单一真源,不另设硬编码);
   **不重试**(查询尽力而为,失败即降级态)。

**处理,v1 词表零格**:

- `jsonpath(items)` 提取行集 → 行数截断 → **投影到列集**(`label ∪ 全目录
  绑定列`;绑定关系全在目录 `value_source` 引用里,索引构建时派生——预定义
  列清单免费)。缓存放投影后行,行宽收敛到几百字节,宽行方差消除(§5.3);
- **形状漂移与空结果分离**:items 命中父路径且为空列表 = 合法空结果(缓存);
  **不命中**(父路径缺失/非数组)= 形状漂移 → 按错误处理**不缓存** + 错误条
  "行集提取失败(响应形状漂移?)"——两者语义天差地别,混谈会把漂移误当
  空字典静默缓存;
- **分页语义**:分页端点的视图 = 首页(行数受声明缺省 page_size 限制,到不了
  MAX_ROWS 是正常态);要更多行调大视图 params 的 page_size;
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
| `STALE_MAX_WINDOW` | 24h | stale-while-error 回退窗;超过即真降级 |

- **惰性过期**:读时判 TTL,过期即 miss 重取;无后台线程;
- **LRU 容量逐出**:命中 `move_to_end`,溢出 `popitem(last=False)`;
- **错误永不写成新条目**;**空结果缓存**(items 命中且为空列表 = 合法答案);
  **形状漂移不缓存**(父路径不命中 = 错误,§4.2——漂移被当空结果缓存是
  静默错误);
- **stale-while-error**:过期条目不立即丢弃——重取失败时回退**最后一次成功
  行集** + `stale=true` 标记(fetched_at 照实显示),超过 `STALE_MAX_WINDOW`
  才真降级。旧好值在错误窗内继续服务且明确标记:SUT 宕机窗口内配置工作流
  不断炊;
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

**短熔断**(对齐 plate_client 既有熔断模式):同视图**连续失败 3 次 → 30s
熔断窗**,窗内直接降态不再打 SUT(refresh=1 同受约束)——防连点把垂死的
SUT 或被踢的凭证刷爆。~6 行。

### 5.3 内存上界

64 视图 × 200 行 × 0.2-0.5KB/行(**投影后**行宽,§4.2——几列标量,宽行
方差消除)≈ **2.6-6.4MB 理论上限**。有界即可接受。**不引 Redis**:multi-worker
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
`setValue(row[column])`**(既有 body 写入通路 + D8 剪枝,零新写值机制);
**缺列跳过**:行缺某绑定列 → 该字段不写、保留现值,行内该列显示
"--"(稀疏行不产生 undefined 脏写)。例:选一条待委托订单 →
bl_no/客户/容器等绑定字段全落。

选择器顶部常驻**本地过滤框**(行内子串过滤,纯前端零上游,词表红线不涉;
N=1 与 N>1 同用)——200 行内客户端过滤够用,服务端检索留给词表准入重议
(§12.2)。

### 7.4 B-现钉 = 同一机制

与 A / 一查多填共用"查→选→写字面量",**无独立代码路径**;区别仅语义记账
(存在性依赖的值会腐烂,边界表 §9,逃生门 = 活查 §8)。

### 7.5 值语义:非注入

**"注入"在本仓指 carry_injection(运行时自动物化)——本功能永不注入。**
流程恒为:渲染候选 → 用户显式选择 → 写字面量;保存即所见,产物自含。
选择落值后行内显小徽标「view:<name>」(title 带 fetched_at),服务腐烂排查;
纯 UI 态,零新增存储。降级态(视图 404 / 凭证过期 / SUT 不可达)= 选择器
错误条 + **认证页直达链接**,**绝不自动重登录**(凭证维护主体可能是管理员
而非当前使用者——链接把干等变成引导)。

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
| 平台用户鉴权面 ≠ SUT 凭证权限面 | 任何平台登录用户可借查询凭证的 SUT 权限取数 | 内网接受,不设机制;对外暴露前重议 |
| 分页端点视图 = 首页 | 行数受声明缺省 page_size 限制,到不了 MAX_ROWS | 语义明示(§4.2);要更多行调大视图 params 的 page_size |
| 词表蔓生 | "再处理一下"逐格腐蚀解释器 | DSL 红线(§4.3),准入需重评审 |
| 双通道投影一致性窗 | /full(前端开 composer 拉)与 /api/query-views 索引(后端 memo)= 同一 plate 状态的两时刻两投影 | 命名不可变(§3.5)+ memo TTL + 熔断;失败 = 无害降级,非数据错误 |
| 钉值来源不持久化 | 场景 JSON 只有字面量,无从考证来自哪个视图/时点(徽标纯 UI 态,§7.5) | 排查靠值本身 + git 历史;持久化需增场景 schema 键,v1 有意识不做 |
| 查询端点双重角色 | 目录化查询端点既是被测对象又是配置工具——端点本身有错,作者就在错的值域里选 | 端点质量 = 配置质量上游;golden + 端点自身场景测试兜底 |

---

## 10. 测试矩阵

| # | 层 | 用例 |
|---|---|---|
| ① | plate 模型 | QueryView 形状校验;聚合层:view name 全局唯一 / value_source 引用闭合 / enum×value_source 互斥 / 非 GET 挂视图须 query_safe / 视图参数闭合(必填缺 → 构造期拒;"缺" = 双 None) |
| ② | plate wire | /full 携带 query_views + value_source;/api/query-views 聚合完整性(含 columns 派生与合并后 params);golden 意识性重钉(含索引投影) |
| ③ | platform 组装 | GET/POST 分流;params 合成链(view▸default▸example)与键语义(覆盖已声明/追加未声明/可选缺省不携带);缺必填 422;非 GET 未声明 query_safe → 422;服务解析 + token 注入;超时与鉴权跟随 ApiSpec |
| ④ | platform 缓存 | TTL 惰性过期 / LRU 逐出 / MAX_ROWS 截断 / 空列表缓存与漂移不缓存分形 / 错误不写成新条目 / refresh 旁路 / stale 回退与 STALE_MAX_WINDOW |
| ⑤ | platform 并发 | 同视图并发单飞(1 上游请求);同凭证跨视图串行;连续失败熔断窗;锁序无死锁冒烟 |
| ⑥ | platform 凭证 | 401 → 降级提示不重登录;CurrentUser 鉴权门 |
| ⑦ | 前端 | enum 分支优先级(ui_kind=text + enum → select);折叠区同款;number enum 写值类型;选择器行渲染 + 行扇出写值 + 缺列跳过 + 本地过滤;N=1 单写;降级态(认证页直达) |
| ⑧ | 回归 | 三套件 + vue-tsc 0;dispatch 基线零漂 |

---

## 11. 验收清单

- [ ] 费用名称字段:打开选择器 → 130+ 费用字典全列 → 选择 → 字面量落 body;
- [ ] 待委托订单一查多填:选一行 → bl_no/客户/容器等绑定字段全落;
- [ ] 静态 enum 字段(active_tab/action/sort_order)渲染为 select;number 型
      enum 写值为 number 非 "1";
- [ ] /full golden 重钉入库;dispatch 基线零漂;
- [ ] 查询凭证过期 → 选择器提示 + 认证页引导,无自动重登录;
- [ ] 非 GET 端点未声明 query_safe 挂视图 → 构造期拒 + 路由 422 双保险;
- [ ] SUT 停机窗口内:选择器回退最后成功快照(stale 标记 + 原 fetched_at)
      不空白;超 STALE_MAX_WINDOW 真降级;
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
