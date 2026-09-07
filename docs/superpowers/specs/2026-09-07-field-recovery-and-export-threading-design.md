# carry 字段找回与导出解析态穿线 设计

> 状态:已立项待实施(2026-09-07 评审,09-05 spec §10.0 + §10.6 合并立项)
> 前置:2026-09-05 field-state-catalog 已全量落地(M1-M3 绿);本设计是其 §10 挂账的活跃窗口。

---

## 0. 背景与问题

### 0.1 问题 A:字段状态控制单向残废(挂账 #0)

§1.3 护栏承诺"场景覆盖即时生效、定错不堵人不发版",实际只兑现了一半:

- 状态下拉(FieldStateSelect)只挂在**渲染行**上 —— FieldForm 行尾;
- carry 条目不进渲染树:`declarations.ts` buildNode 对解析态 carry 直接
  `return null`(祖先吸收,整棵剪除);
- ⟹ **carry → form/collapse 无 UI 路径**。切进 carry 的字段(以及 plate 共识
  默认 carry 的字段,如备注族)从表单上消失后无法找回,只能手改 JSON;
- 更隐蔽的一层:**行尾下拉也无法 carry 容器**。§3.5 校验的
  `tree_inconsistency`(carry 容器 ⇒ 子孙必 carry)会拒掉"容器 carry +
  form 子孙"的合成态 —— 现行单条增量写入下,想 carry 整容器必须先把每个
  子孙逐条 carry(顺序苛刻,用户不可发现)。

**定性**:不是技术障碍,是 §5.4 搜索框在任务规划(§6-M2-3)中遗漏 +
悬账未登记(仅存 FieldStateSelect.vue 组件注释),09-07 评审补登为 §10.0。

### 0.2 问题 B:导出面与配置面不一致(挂账 #6)

状态解析链 `state(path) = step.field_states[path] ?? entry.state ?? 'form'`
的各消费方兑现度:

| 消费方 | join 增量? | 位置 |
|---|---|---|
| composer 表单定面(前端 buildTree) | ✅ | `declarations.ts` buildTree(field_states 入参) |
| 运行时注入(平台后端) | ✅ | `carry_injection.py` `carry_face(decls, step.field_states)` |
| 导出侧 carry 物化(平台后端) | ✅ | `scenarios.py` convert overlay 与 dispatch 共用 `build_carry_context`(同源) |
| **plate 导出定面** | ❌ | `export/platform.py` `_render_request_view`:面基准 = entry.state |

缺口根因:平台场景 definition 发往 plate convert 时,plate `schema/step.py`
Step 模型**没有 field_states 字段**(pydantic 默认 extra=ignore 静默剥除,
`plate_client.py:132` / 前端 `types/plate.ts:306` 注释均已自认)。导出器
从 Step 上拿不到增量,只能读共识默认。

**后果**:场景把字段 form→carry 后,composer 不渲染、dispatch 不注入,但
plate 导出产物仍给它补默认值进 body、登记进 fields_meta(读 entry.state
=form);carry→form 反向同理。**平台内执行无恙(注入已 join),导出的
gimbal 场景独立执行时 carry 面与配置意图分歧**。随 field_states 采用率
增长,分歧面线性放大。

### 0.3 需求追溯表(讨论要义 → 设计落点)

| 预期 | 落点 | 章节 |
|---|---|---|
| 增加搜索框查询字段,查到即可切状态 | FieldStateSearch:全量目录语料(含 carry)+ 结果行状态控制 | §2.1/§2.2 |
| 搜索框是定位手段,不是添加机制(已拍板) | 只改既有字段的状态,零"添加清单"语义 | §2.2 |
| 切走(carry)能切回(form/collapse) | 双向级联增量 + 统一写入通路 | §2.3 |
| 导出产物诚实反映场景配置意图 | plate Step 收编 field_states + 导出面切解析链 | §3.2/§3.3 |

---

## 1. 目标与非目标

**目标**

1. carry 字段可找回:搜索框扫全量目录(含 carry 语料),命中行直接切
   状态,写 step.field_states 增量(与行尾下拉同通路);
2. 状态写入支持**级联批量增量**:surface 深层字段自动拉起 carry 祖先,
   carry 容器自动压平子孙 —— 顺带修复行尾不能 carry 容器的隐性缺陷;
3. plate 导出定面切解析链:导出产物面 = 合成态,与 composer/注入/物化
   三处一致;存量场景(无增量)导出**逐键零漂**。

**非目标**

- 响应面状态控制(响应面单脸,state 无视 —— 09-05 §2.6,挂账 #5 观望);
- 装饰词表(语境 label/默认值等,挂账 #4;本设计搜索行写下拉即天然留缝);
- absorb CLI / L1/L2 / L3(独立触发器,见 09-05 §10 重写表);
- gimbal 执行核零改动(resolver/jsonpath 不碰,与 09-05 同纪律);
- 平台后端解析逻辑改动(注入/物化已 join,本设计平台侧预期零代码变更,
  仅回归验证)。

---

## 2. 设计 A:字段状态搜索框(#0)

### 2.1 语料与匹配(纯函数,declarations.ts)

```
searchCorpus(declarations, fieldStates?): Array<{
  path, name, description, type,
  resolved: FieldState,          // 解析态(resolveState)
  overlay: boolean,              // 有显式增量(FieldStateSelect ↺ 语义)
  breadcrumb: string,            // 祖先 name 链($.a › b[0] › c 式)
}>
```

- 语料 = **iterFlat 全量展开**(children 树先序),**不按状态剪除** ——
  carry 正是"搜索语料"(09-05 §5.4 原话);容器条目也在列(可整树切面);
- 匹配:name / path / description 大小写不敏感子串;空查询 = 不出结果面板
  (避免全量清单淹没了"定位"语义);
- 语料上限提示:命中 > 50 条时折叠为前 50 + 计数(200+ 字段端点的防淹)。

### 2.2 组件与挂点

新组件 `FieldStateSearch.vue`,挂 Canvas **请求签** FieldForm 下方的
hint 行区(`field-form-hint` 同排或紧邻)—— 不进 FieldForm 本体
(FieldForm 是值×结构渲染器,状态搜索是配置意图入口,职责分离)。

- props:`corpus`(Canvas 预计算,含解析态);
- emits:`apply: [increments: Record<string, FieldState>, origin: {path, target}]`
  —— 一次级联写入 = 一个增量批;
- 结果行复用 `FieldStateSelect`(现成三态下拉 + ↺ 重置,`overlay` prop
  直连语料行标记);行左侧 path 面包屑 + 解析态徽标 + required/DESCRIPTIVE
  警示点(与 §3.5 软警告同词表,Canvas 侧只展示不裁决)。

### 2.3 级联增量规则(核心决策)

新纯函数 `cascadeIncrements(declarations, fieldStates, path, target)` →
本批应合并的增量(单事务)。两条规则,维持 §3.5 合成态不变式:

| 操作 | 规则 | 依据 |
|---|---|---|
| **surface**(target = form/collapse) | ① `increments[path] = target`;② path 的每个**解析态为 carry 的祖先容器** `increments[ancestor] = 'collapse'` | 祖先不拉起则子树在 buildNode 剪除,切换不可见;祖先落 collapse(而非 form)= 最小侵入布局 —— 容器成为折叠区而非爆开主表单 |
| **sink**(target = carry) | ① `increments[path] = 'carry'`;② path 的每个**解析态非 carry 的子孙** `increments[descendant] = 'carry'` | `tree_inconsistency` 不变式:carry 容器 ⇒ 子孙必 carry;子孙按解析态判(默认 form 或显式 form 增量都要压) |

边界与语义:

- **容器 surface 不动子孙增量**:collapse 容器下子孙 carry 合法(局部
  传递),已显式表达的意图保留;反向 sink 才压平;
- **祖先已有显式 carry 增量 → surface 覆写为 collapse**:用户最新意图胜
  (与行尾下拉同语义:切了就是切了);
- **写入值与解析态相同仍写显式增量**(overlay 标记 + ↺ 可回),与行尾
  下拉现状一致 —— 显式覆盖是"场景表达过意见"的凭据(§3.3 漂移保护);
- **行尾下拉同换此通路**:Canvas `onFieldState` 改为调
  `cascadeIncrements` 再批量落地 —— 修复"行尾 carry 容器被校验拒绝"
  的隐性缺陷(0.1)。搜索行与行尾从此共用一条写入路径,零分叉;
- ↺ 重置:仅清**该 path 自身**增量(祖先/子孙增量保留 —— 它们是用户
  分别表达过的意图);重置后解析态回落 entry.state。

### 2.4 写入与校验(批量乐观 + 整批回滚)

Canvas 现行 `onFieldState`(乐观写 → `validateEndpointFieldStates` →
违例回滚)扩展为批量形态 `applyFieldStates(increments)`:

1. 快照 `before = { ...step.field_states }`;
2. 合并增量(map 覆写);合并后为空 → `delete step.field_states`(§3.1
   默认零存储语义保持);
3. 调 §3.5 校验(整批合成态一次裁决 —— 级联设计的目标正是让合法批
   一次通过,而非多步各拒);
4. errors 非空 → 回滚快照,结果面板行内提示(错误条目 `code/path`)。

### 2.5 交互细节

- 搜索框 placeholder:`搜索字段(含 carry 传递面)`;
- 结果行布局:`面包屑 › name` + type + 解析态徽标 + FieldStateSelect;
- 命中 carry 行给视觉区分(徽标灰),form/collapse 行不特殊化;
- 输入防抖 200ms;ESC / 失焦清面板;查询词高亮不强求(v1 不做)。

---

## 3. 设计 B:plate 导出解析态穿线(#6)

### 3.1 链路与缺口(精确图)

```
platform PG(definition JSON,steps[].field_states)
  → plate_client convert(preview/export 路由,发送前补 plate 必填默认)
    → plate Scenario.model_validate     ← ★ Step 模型剥 field_states(0.2)
      → PlatformScenarioExporter.to_view
        → _render_request_view(s.request, ep)   ← ★ 面基准 entry.state(platform.py:592 调用点)
  ← converted{consumer, converted}
  → convert overlay:carry 物化(build_carry_context,已 join 增量,不动)
```

两处 ★ 即全部改动点;overlay 物化与 dispatch 同源已 join,零改动。

### 3.2 plate Step 收编 field_states

`gimbal_plate/schema/step.py`:

```python
field_states: Optional[dict[str, str]] = Field(
    default=None,
    description="场景侧字段状态稀疏增量(path → form/collapse/carry;"
                "平台配置意图,09-05 §3.1)。plate 唯一消费点 = 导出定面"
                "(export/platform.py 解析链);None/空 = 读穿共识默认",
)
```

- **wire 语义**:进 = 平台发definition 时不再被剥;出 = 导出器可读。
  不进 endpoint 目录(io_spec 不动),不进 golden(io_declarations fixture
  覆盖 /full 端点面,与 Step 无关);
- **序列化纪律**:仅非 None 携带 —— Step 直 dump 处用 `exclude_none`(或
  条件注入),保证**存量场景 wire 逐键零漂**(dispatch 基线 exports/
  convert 两节对拍,验收硬门);
- 平台侧类型(`types/plate.ts` StepFieldStates)已有,零前端改动;
- gimbal 执行核读 Step 时多一个未知键:pydantic/gimbal 侧均为 tolerate
  形态(执行核 ${} 解析不读此键)—— 若 gimbal Scenario 校验 strict 则
  平台导出时继续剥(导出产物本就不该携带配置意图;见 3.4)。

### 3.3 导出面切换(export/platform.py)

- `_render_request_view(request, ep)` → 增第三参 `field_states: Any = None`
  (调用点 platform.py:592 从 `s.field_states` 穿入);
- plate 侧新增 5 行镜像 `resolve_state(path, entry_state, field_states)`
  (与 platform `field_state_resolution.resolve_state` 同式:增量 dict 形状
  防御 + 词表校验 + `?? entry_state ?? 'form'`)。**跨仓镜像纪律**:三处
  实现(plate export / platform backend / 前端 declarations.ts)同改动、
  同测试用例形状(09-05 §3.2 单一实现原则的跨语言边界声明);
- 面语义(全按**解析态**):
  - carry 面(含整容器):不补默认,仅透传 body 已有字面量(现状语义,
    基准换解析态);
  - form/collapse 面:body 补全(default → example → None 链,D7 深层无
    None 骨架,平铺 None 占位 —— 全不动);
  - fields_meta:登记面 = 解析态非 carry 的顶层条目;**条目内 state
    字段 = 解析态**(合成态诚实,前端 O(1) 查表语义不变);
- `PlatformEndpointView.request_fields`(端点级聚合,无场景语境)维持
  entry.state 读穿 —— 端点级是共识默认的领地(与值表路由同口径);
- `export/gimbal.py` 无面逻辑(grep 验证零 state/carry 命中),不动。

### 3.4 平台侧与导出产物

- 平台后端:**预期零代码改动**。注入(carry_injection)、物化
  (build_carry_context)已 join;convert 请求天然携带 definition 原文
  (field_states 随 steps 进 plate,3.2 后不再剥);
- 导出的 gimbal 产物:**不含 field_states**(配置意图在导出面已物化为
  终态 —— body/fields_meta/carry 透传,产物自含执行语义,无需携带意图
  本身)。若 gimbal 侧 Scenario 校验对未知键 strict,在 exporter 输出前
  exclude(实现时验证,预期 pydantic 容忍不触发);
- 回归验证项(不是改动项):同场景 preview-plate 产物 ≡ dispatch 物化
  终值(09-04 §8 黄金等价延伸到解析态口径)。

### 3.5 A/B 对拍与基线纪律

- **存量零漂**:无增量场景(全部现网场景)导出必须与切换前逐键相等
  (读穿等价,09-05 M3 同款论证);dispatch 基线
  `tools/ab_dispatch_dump.py` 六节对拍,exports/convert 节零 diff;
- **增量语料用例**:构造带 field_states 的 fixture 场景(新 fixture,不
  动存量),单测钉四象限:form→carry / carry→form / 容器整 sink /
  深层 surface;
- golden(io_declarations)与 dispatch 基线 fixture 均**不重钉**(本设计
  不改端点目录、不改存量行为)。

---

## 4. 测试矩阵

| # | 层 | 用例 | 阶段 |
|---|---|---|---|
| ① | 前端纯函数 | searchCorpus:含 carry 语料 / 解析态与 overlay 标记 / 面包屑;cascadeIncrements:surface 拉祖先(collapse)/ sink 压子孙 / 祖先显式 carry 覆写 / 同值显式增量 / 目录外 path 防御 | A |
| ② | 前端组件 | FieldStateSearch:过滤 / 空态 / 命中行 apply 上抛;FieldStateSelect 复用(↺) | A |
| ③ | 前端集成 | Canvas applyFieldStates:批合并 / 校验失败整批回滚 / 清空删键;行尾下拉走级联(carry 容器一次成功) | A |
| ④ | plate 模型 | Step 收编 roundtrip(field_states 保留)/ None 序列化不携带(wire 零漂) | B |
| ⑤ | plate 导出 | _render_request_view 四象限(3.4)/ 端点级 view 不受影响 / fields_meta state= 解析态 | B |
| ⑥ | 对拍 | dispatch 存量零漂六节对拍 / 带 fixture 增量场景 preview ≡ 期望终态 | B |
| ⑦ | 套件门禁 | plate / backend / frontend + vue-tsc 0 全绿 | A+B |

任务依赖:A(前端链)与 B(plate 链)无相互依赖,可并行;A 内部
①→②→③,B 内部 ④→⑤→⑥。

## 5. 验收清单

- [ ] carry 字段可经搜索框切回 form/collapse(含 plate 共识 carry 的备注族);
- [ ] 行尾下拉 carry 容器一次成功(隐性缺陷修复);
- [ ] 级联后合成态通过 §3.5 校验;校验失败整批回滚;
- [ ] field_states 增量随 definition 进 plate 不再被剥;
- [ ] 导出面 = 解析态:form→carry 不补默认/不进 fields_meta,carry→form 补全+登记;fields_meta.state = 解析态;
- [ ] 存量场景(无增量)导出逐键零漂,dispatch 基线零重钉;
- [ ] 端点级 request_fields 维持共识默认(读穿口径不变);
- [ ] 三套件 + vue-tsc 0 全绿(⑦)。

## 6. 挂账(本项目产生)

1. **搜索结果行装饰缝**:语境 label/readonly/默认值(09-05 §10.4 观望票)
   —— 搜索行结构已预留(面包屑 + 徽标 + 下拉),认领时零结构改动;
2. **响应面搜索定位**:响应树大时的字段定位(纯 locate,无状态切换)——
   等响应面可配置(§10.5)一起定价;
3. **gimbal 侧 Scenario 对 field_states 键的容忍性**:3.4 预期 pydantic
   容忍,实现时实测;若 strict 则导出 exclude(预计 1 行)—— 落地时销。
