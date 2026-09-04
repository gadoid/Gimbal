# 场景级 binding 配置 — channel 退役与配置器化设计

> 状态:**设计定稿待评审**(2026-09-04,与编排者四节对齐后落稿:存储模型 → split 归属 → 消费面 → 迁移,含装饰缝裁定)
> 日期:2026-09-04
> 前置:IO 声明归一化(2026-09-01 spec,P3 已执行 —— declarations 单一承重真源);carry 存储与注入(2026-08-31,已落地)
> 分支:待 `feat/io-declarations-and-strategy-badges` 合入 main 后开出(本役依赖 declarations 单源前置)

---

## 0. 背景与动机

### 0.1 核心需求(用户钦定)

1. **platform 本质上是一个配置器** —— 其价值在「配」,不在「承重定义」;
2. **不同场景需要 binding 的字段可能不一致** —— form 面是场景意图,不是接口属性;
3. **plate 不应该决定每个字段是否必要配置** —— 该决策属于实际业务(场景编排时点);
4. 由此推论:channel 定错的修复成本应从「plate 代码变更 + 发版」降为「platform 配置编辑即时生效」。

现状:channel(binding/carry)是字段**唯一的表单行为轴**,钉死在端点契约里(`DeclarationEntry.channel`)。「同一端点在不同场景配不同 form 面」结构性不可能 —— 需求憋在闭合模型里,只会以游离结构的形式破土(恰是 B7 落点闭合当初要防的反向路径:闭合的合法性来自能满足真实需求,不是反过来)。

### 0.2 规模事实(2026-09-02 重钉口径,本役迁移量依据)

| 事实 | 数量 |
|---|---|
| 端点总数(fin 17 + account 1) | 18 |
| 声明总数 | 631 = 532 binding + 99 carry |
| 委托订舱 order_entrust_order_add | 3 binding + 91 carry(样板的来源,schema 非空) |
| 空 schema 端点(`schema_={}`)且带 carry | order_order_add(3 carry)、order_order_book(4 carry) |
| `$.action` 通道分歧实例 | entrust_order_add = binding(default='check');order_book = carry —— 逐端点知识真实存在,但归属配置层后天然各自表达 |

### 0.3 已否决的形状

| 形状 | 否决理由 |
|---|---|
| 甲:plate 留 channel 当默认 + step 只记偏差(便宜版) | 双 split 机制并存 = 双真源气味(上代腐化死因);字段翻进 carry 需要 type → 532 条回填躲不掉,省的只有 18 文件改写与 golden 重钉;与「一次性切换」哲学相悖,将来收尾等于付两次 |
| 乙:差集宇宙 = schema properties | 空 schema 端点(order_order_add/book)carry 面算空,B2 carry 自持被破坏 —— 用户模型「每字段全持有」天然选定**清单为宇宙**,与 schema 无关 |
| 丙:plate 按请求参数投影(`/full?bindings=...`) | binding 集本就住在 platform,差集是平凡集合减法,没必要让配置穿线过 plate 再回来;plate 保持零参数纯目录 |

### 0.4 实现裁定(2026-09-04 评审结论)

**做,一次到位,不分层过渡。** 收益/代价已对账:核心需求真实且现状结构性堵死;刚完成的归一化恰好把改造成本压到最低(单轴修改);被换掉的三个结构保证各有等效缓解且显式定价(§7)。排期:当前分支合入 main 后启动;若 RunDialog TRACK 票 / PG 迁移绑定项欠账利率更高,先清再启动。

---

## 1. 设计原则(硬性)

| # | 原则 | 内容 |
|---|---|---|
| 1.1 | 四层归位 | plate = 目录(身份元数据)/ platform = 配置器(语境决策)/ 值 = 环境(可变,值表)/ split = 意图(随场景冻结) |
| 1.2 | 落点闭合重述 | 请求字段仍二分闭合:**step.bindings 内 = form 面(body 自有值),其余 = carry 面(值表注入)**。比旧三分类(binding/carry/Type C)更干净,Type C 作为 schema 残余第三落点保留(§2.4) |
| 1.3 | 归属铁律 | 身份元数据归 plate 目录(type/required/enum/description);语境装饰归 platform 配置。冲突解析方向恒为 **config > catalog**(与值表解析链 body > 绑定 > 默认同构) |
| 1.4 | B6 重表述 | 从「存储禁值」变「**投影剥值**」:字段级 default/example 是表单角色元数据,存储合法;注入侧只读 path/type,值表仍在 platform —— 值不回流的语义不变,保证点从构造校验后撤到消费纪律(§2.3) |
| 1.5 | 一次性切换 | 适配完全部存量(含场景数据回填)后单部署翻面,内网单体无错配窗口;不做长期双轨 |

---

## 2. 存储模型(plate 侧)

### 2.1 DeclarationEntry 去 channel

```python
class DeclarationEntry(BaseModel):
    name: str
    path: str
    type: str                      # 升格:全条目必填(§2.2)
    required: bool = True
    default: Any | None = None     # 表单角色元数据,全条目合法(§2.3)
    example: Any | None = None     # 同上
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: ... = "unknown"       # 暂留目录(§2.6),装饰缝将来可覆写
    source_kind: ... = "independent"
    assertable: bool = False       # 仅响应侧有意义,保持
```

- **channel 字段退役**,随之下列校验全数消亡:B7 通道-规格闭合、B5 type 仅 carry 必填、B6 carry 禁值、D2/D3 通道形态与包含规则(其中通道形态规则迁往配置编辑时,§3.4);
- **双角色元数据按需携带,无角色约束**:carry 系字段保持稀疏(type+description),binding 系字段照旧带 default/example/ui_kind —— 「全持有」是能力不是义务;
- path 校验不变(is_valid_path → normalize,任意合法 JSONPath 含 FIELD/INDEX);name 别名制不变。

### 2.2 type 全条目必填

任何字段都可能被配置翻进 carry 面,注入需要 type(宽松类型转换)→ type 必须目录级齐备。**迁移量:532 条今日 binding 条目补 type**(schema 节点吸收脚本,语料里基本都有;吸收不到的显式补)。

### 2.3 B6 投影剥值

- default/example 在目录中合法(它们本来就是今天 binding 条目的既有内容,如 'Codfish_TEST_001');
- carry 面 = 差集投影,**注入与值表语义不消费 default/example**(代码事实:注入只读 path/type);
- 软 lint(挂账):配置把带 default 的字段划入 carry 时,配置页告警「default 仅表单角色生效,值仍以值表为准」。

### 2.4 Type C 残余保留

不在目录清单的字段不进宇宙:form 面仍含 schema 差集渲染(step body 直填),第三落点不死。form 面 = `step.bindings ∩ 目录` ∪ `(schema − 目录)`。

### 2.5 响应面:view_only 随 channel 消亡,单脸不变

响应声明本就全部 view_only,无 split 可配 —— channel 键从响应条目消失后,响应面 = 目录单脸 + assertable 标记,语义零变化。响应字段的可配置展示/断言(按场景挑断言面)为远期挂账(§9.5),本轮明确不动。

### 2.6 ui_kind / source_kind 暂留目录

两者偏表单行为,理论上是语境装饰 —— 但 v1 无覆写需求,留目录作基线值,装饰缝(§3.5)将来可覆写。归属铁律不破坏:它们是「无语境时的缺省渲染提示」。

---

## 3. split 归属(platform 侧)

### 3.1 step.bindings 是权威

- step 顶层新增 `bindings: list[str]`(归一化 path,与 api/request/strategy 平级 —— 它描述 step 的配置意图,不是请求体内容);
- 四个消费方(composer 表单 / dispatcher 注入 / export 物化 / replay)读**同一份** —— split 随场景资产走,不依赖任何全局配置的时点;
- 差集:`carry 面 = {目录 path → type} − set(step.bindings)`。

### 3.2 端点默认配置:只作编排预填

```
endpoint_binding_sets(PG 新表)
  id PK / endpoint_id uniq / field_paths JSON(list[str])
  updated_by / updated_at
```

- 新建 step 时预填自端点默认集,改过即冻结进 step;
- seed = 今日各端点 binding 面(532 条换算 18 份集合);
- **配置表不服务运行时**:carry_injection 从 step 取 bindings,不查此表(查表的只有编排预填与值表候选面 §4)。

### 3.3 缺省与防御

| 情形 | 行为 |
|---|---|
| step.bindings 缺失(手写 JSON 裸奔/异常数据) | 回落端点默认配置(一行规则,非兼容债) |
| 端点默认配置也缺失(新端点未配) | 全 binding(等价 carry 面 ∅)—— **fail-closed:什么都不注入**;carry 必须配置显式开通 |
| step.bindings 含目录外 path | 交集容忍(忽略),composer 显示 stale 警告 |

### 3.4 配置编辑校验(从 plate 构造校验迁入)

| 校验 | 规则 |
|---|---|
| carry 形态 | 划出 form 面(即入 carry)的 path 须平铺/dot(整容器传递,值表存容器 JSON)—— 原 D2 通道形态规则的配置侧继任 |
| 容器/子孙不同主 | carry 面内的容器 path 与 form 面内其子孙 path 不得并存(配置编辑拒)—— 原 D3 包含规则的配置侧继任;否则容器注入与叶子 body 值的合并语义无定义 |
| required 落 carry 软警告 | `$.bl_no` 类必填字段被划出 form 面 → 提示「确认值表有兜底,否则请求必挂」 |
| DESCRIPTIVE 软警告 | 备注族(remark/notes/cancel_remark 词表,platform 常量,seed 自 plate 政策测试)进 form 面 → 提示 —— `TestCarryFacesAllEndpoints` 政策守卫的软着陆 |

### 3.5 装饰缝(seam-only,v1 只留缝不建词表)

- **bindings 形状声明为 map-兼容**:`list[str]` 是 `{path → 覆写键}` 的 keys-only 退化形态;将来升级纯加性,差集算法一个字不改(keys 即当年集合);
- 级联与归属铁律见 §1.3;**工程红利:装饰住在 platform 侧,plate wire 形状不动 → golden 永不因加装饰而抖** —— 反之把装饰堆回 plate 条目,每加一词表就是一次 18 文件 + golden 重钉,添加成本两端差一个数量级;
- 候选词表备档(认领制,出现真实 UX 需求再建):`order`(排序)/ `group`(分组)/ `when`(条件显隐)/ `readonly` / `label` 覆写 / 前端校验规则 / 语境默认值。

---

## 4. 消费面改造

| 消费方 | 现状读法 | 新读法 |
|---|---|---|
| `carry_injection._carry_face` | /full 过滤 `channel=="carry"` | /full 读**全量目录**(path+type)− `step.bindings`(从 step 取)。降级语义不变:plate 挂 → 空面 → 不注入;T8 索引契约不动 |
| carry 路由 `service_fields`(值表配置页候选面) | carry 通道条目 | 目录 − **端点默认集**(查 endpoint_binding_sets)—— 值表是环境级,候选面跟默认配置走,不跟单场景走 |
| composer 表单 | declarations 按 channel 投影 | form 面 = `step.bindings ∩ 目录` + Type C 差集(§2.4);carry 徽标 = 差集;**新增字段挑选器**(增删 form 面,自由配置的操作面) |
| `field_defaults`(plate action) | 按 binding 通道出默认值 | 全量出目录默认值,**platform 按 step.bindings 过滤**(plate 连 action 都不带参数,纯目录贯彻到底) |
| `export/platform.py` | 迭代 request carry 面透传字面量 | carry 面由调用方传入 step.bindings,或返回全目录由 platform 差集 —— 实现期看调用链定夺(挂账 §9.3) |
| `adaptation_ops._field_map` 等 | 按轴 grep 盘点 | M2 任务步骤:按「读 channel 的轴」全量 grep 盘点,逐一给落点(沿用上役「表过时是常态,轴漏读才是事故」纪律) |
| 18 个端点文件 | channel 逐条钉死 | 去 channel 改写 + 532 条 type 回填(脚本辅助);`declare()` 糖 carry 参数退役,bindings 变目录生成 |

---

## 5. 迁移(分支内分段验证,master 一次切换)

### M1 — plate 目录化

1. io_spec:去 channel、type 全必填、§2.1 所列校验消亡、declare() 糖改造;
2. 18 文件脚本改写 + 532 条 type 回填;
3. golden 全量 re-baseline(新形状:条目无 channel、type 全备)—— fixture 入库,意识性重钉,杜绝测试自适应吸收。

**门禁**:plate 套件全绿 + golden 新基线入库。

### M2 — platform 配置器化

1. PG ×2:`endpoint_binding_sets` 建表(seed 18 份 = 今日 binding 面);存量 step.bindings **一次性回填**(每 step = 其端点当日 binding 面,全量计数断言 + 抽样对拍);
2. 四线切读:carry_injection / carry 路由 service_fields / field_defaults 消费 / export(按 §4);
3. composer:form 面改源 + 字段挑选器 + 双软警告(DESCRIPTIVE / required 落 carry)+ carry 形态配置校验;
4. channel 读取轴全量 grep 盘点(adaptation_ops 等)。

**门禁**:backend / frontend 套件 + vue-tsc 0 全绿。

### M3 — 对拍验证与切换

1. 三套件全绿(基线以切换时点实测重钉,允许 ±新增用例);
2. **A/B 对拍**:切换前后同批场景 dispatch 物化终值全等(上役 HEAD↔工作树对拍同款方法);dispatch 基线(当前口径 901=570+331)重钉;
3. 切换:单部署翻面。**回滚 = revert 部署**(PG 变更全加性,旧代码无视新表/新字段)。

---

## 6. 测试矩阵

| # | 测试 | 内容 | 阶段 |
|---|---|---|---|
| ① | golden 新形状 | 全 18 端点 /full declarations:无 channel、type 全备、余键与今日等价 | M1 |
| ② | 差集单元 | carry 面 = 目录 − bindings;含空 bindings / 缺省回落 / 端点配置也缺 → 全 binding(fail-closed)/ 目录外 path 交集容忍 | M2 |
| ③ | 回填断言 | 全量 step.bindings == 端点当日 binding 面(计数 + 抽样) | M2 |
| ④ | A/B 对拍 | 切换前后同批场景 dispatch 物化终值全等 | M3 |
| ⑤ | 降级语义 | plate 不可达 → 空面不注入(fail-closed 保持) | M2 |
| ⑥ | 配置校验 | 非平铺 path 划入 carry → 拒;DESCRIPTIVE / required 软警告触发 | M2 |
| ⑦ | roundtrip | step.bindings 随场景导出/导入保形 | M2 |
| ⑧ | 三套件基线 | plate / backend / frontend + vue-tsc 0 | 各段门禁 |

---

## 7. 风险表

| 风险 | 缓解 |
|---|---|
| carry_injection 是运行时关键路径 | A/B 对拍护送(④)+ 降级语义不变(⑤)+ T8 索引契约不动 |
| 全局默认同名 path 泄漏面变宽(carry 面默认宽于今日契约审查面) | 值表门控兜底(无值不注);真泄漏仅限与全局默认同名的 path(`$.remark`/`$.action` 类);漂移告警挂账(§9.2) |
| B6 弱化为消费纪律 | 注入只读 path/type 的代码事实 + 软 lint(§2.3) |
| 存量 step 回填错漏 | 全量计数断言 + 抽样对拍(③) |
| golden 重钉的自适应吸收 | fixture 入库,意识性 re-baseline 流程(上役同款) |
| 装饰词表过早膨胀 | seam-only 裁定写死本 spec(§3.5),认领制 |
| step.bindings 与目录漂移(端点后续改名/删字段) | 交集容忍 + composer stale 警告(§3.3) |

---

## 8. 验收清单

- [ ] /full declarations 无 channel、type 全备,golden 新基线入库(①);
- [ ] 同批场景切换前后 dispatch 物化终值 A/B 全等(④);
- [ ] 存量 step.bindings 回填完成且计数断言通过(③);
- [ ] fail-closed 语义保持:缺配置端点零注入,plate 不可达零注入(②⑤);
- [ ] 字段挑选器可用:增删 form 面 → step.bindings 冻结;carry 徽标 = 差集;
- [ ] 双软警告 + carry 形态校验生效(⑥);
- [ ] `TestCarryFacesAllEndpoints` 退役,DESCRIPTIVE 词表落户 platform 常量;
- [ ] 三套件 + vue-tsc 0 全绿,dispatch 基线重钉(⑧);
- [ ] channel 读取轴 grep 盘点清零(无残读)。

---

## 9. 挂账

1. **装饰词表**(§3.5 备档):order/group/when/readonly/label/校验/语境默认值 —— 认领制,出现真实 UX 需求再立项;加键 = platform 配置层加性变更,零结构改动。
2. **全局默认同名 path 漂移告警**:值表配置页对「carry 面含与全局默认同名 path」提示 —— 本轮只留风险表登记,不做。
3. **export 穿线方式**:调用方传 bindings vs 返回全目录 platform 差集 —— 实现期看调用链定夺。
4. **配置编辑 UI 落点**:endpoint_binding_sets 的编辑页(CarryConfig.vue 扩展 vs 端点目录页)—— 实现期定。
5. **响应面可配置**(按场景挑断言/展示面):远期,本轮明确不动(§2.5)。
6. **按服务批量编辑 binding 默认集**:配置便利项,需求出现再做。
