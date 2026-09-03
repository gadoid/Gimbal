# 深层路径声明与 name↔path 解绑 设计(spec)

> 日期:2026-09-03 · 分支:feat/io-declarations-and-strategy-badges
> 前置:docs/superpowers/specs/2026-09-01-io-declarations-unification-design.md(declarations 单一真源)
> 案例端点:fin.order_entrust.order_dispatch(supplier 数组深层叶子注入)

## 1. 背景与问题

plate 契约的深层嵌套结构(supplier 数组等)整体作为 json/array 声明,无法对其内部叶子做注入。
要注入深层叶子,需要「自定义名字 + path 关联」的声明,但现行设计卡在三处:

| # | 卡点 | 位置 |
|---|------|------|
| 1 | name 必须等于 path 末段 FIELD → 自定义别名非法 | io_spec.py `_validate_path_name_enum`(L41-44) |
| 2 | `$.order_id` 与 `$.supplier[0].order_id` 末段同名 → name 冲突无防护(前端按 name 建键) | `_check_declarations` 只校验 path 唯一 |
| 3 | 前端 get/set 不支持 `[0]` 下标 → 表单读写不到深层值 | frontend utils/jsonpath.ts(能力边界注释明写) |

**关键事实:运行时已完备** — gimbal/utils/jsonpath.py 的 get/set 完整支持 INDEX(自动建链
FIELD→dict、INDEX→list、越界 pad None),assign target 走 `$.request_body.` + path。
卡点全部在契约校验层与视图层,执行引擎零改动。

## 2. 目标 / 非目标

**目标**
- 深层叶子可声明(binding 通道)、可渲染(表单行)、可注入(assign/菜单/角标/只读态)
- 契约不自破:name 冲突、通道形态、包含关系有显式闭合校验

**非目标**
- 通配/循环注入(`$.supplier[*].x` 每元素覆写)— 运行时 `_set_at` 明拒(gimbal jsonpath L441),属未来 strategy 层特性
- repeating group(数据驱动重复行编辑器)— 容器编辑由 JSON 域 + carry 承担
- 契约编辑 UI、parent 存储字段(见 D12)

## 3. 核心决策

### D1 name↔path 解绑(别名制)

- **name = 全清单唯一的显示别名**(ASCII 标识符 `[A-Za-z_][A-Za-z0-9_]*`),仅供 UI 标签与前端映射键
- **path = 唯一寻址真源**(归一化 JSONPath,含下标)
- 废除 name==末段 规则;`_check_declarations` 新增 **name 全清单唯一**
- 旧规则在平铺时代的真实作用(name==末段 + path 唯一 ⇒ name 唯一)由显式 name 唯一校验继任;
  对存量全平铺契约校验等价、零迁移

### D2 通道 × path 形态边界

| 通道 | path 形态约束 | 理由 |
|------|--------------|------|
| binding | 具体路径:仅 FIELD/INDEX 段;拒 WILDCARD/FILTER/RECURSIVE | 单值表单控件写不了通配位置 |
| carry | 平铺/dot 嵌套;拒 `[` 下标 | carry 语义 = 整容器传递(值表存容器 JSON);run_materialize `_body_set` 亦仅 dot |
| view_only | 不限 | 提取/断言为读路径,运行时 `get_all` 原生支持通配 |

### D3 声明包含关系四格(新增校验)

深层化引入「一条声明的 path 包含另一条」的新维度,闭合规则:

| 外层 ⊃ 内层 | 判定 | 语义 |
|------------|------|------|
| carry ⊃ binding | ✅ | **分层覆写**:carry 打底,binding 行 / assign 运行时覆叶子(dispatch 案例) |
| carry ⊃ carry | ❌ 拒 | 整容器传递语义下嵌套 = 一树二主,materialize 顺序敏感 |
| binding ⊃ binding | ✅ | 同归表单:容器 JSON 域 + 叶子行写同一 body |
| binding ⊃ carry | ❌ 拒 | 容器归表单、叶子归值表,双所有者 |

实现:node 序列前缀比较(plate utils/path.py 暴露 `parse_nodes`;binding 限具体 + carry 限平铺后判定无歧义)。
同 path 跨通道互斥维持原样(path 全清单唯一)。

### D4 三态治理模型(不变量澄清)

「binding + carry = 完整字段集」**今天就不成立**:Type C(schema 声明未入 declarations)一直是第三态
(io_spec.py L77-83 注释、前端「其他字段」区 schema 出身行)。真实不变量:

> 每个字段的治理 = binding(表单)| carry(值表)| Type C(schema)三态居其一;
> 治理方 = **精确命中最深的声明**,未命中归所在容器声明,再未命中归 Type C。

**二级字段 = 可选包含(稀疏治理)**:声明是搭在 schema 上的稀疏面,声明一条叶子 ≠ 接管子树;
不想上表单的字段不声明即可。全包含(声明容器须枚举全部叶子)明确否决。

### D5 渲染模型:无层级平铺

- 一条声明 = 一行,`[0][1][2]` = 平级 N 行,渲染零特判
- **path 角标**:非平铺字段(`path !== '$.' + name`)行标签旁 mono 路径小字,平铺字段不加
- **parentPath 投影派生**(D12):角标带治理标注,如 `supplier[0].order_supplier_id · 上级 $.supplier(carry)`
- 派生行按容器前缀聚簇,同容器行相邻;层级分组 = 纯展示层后手(连续同前缀分桶),不进本批
- 理由:表单是值录入面不是结构编辑器 — 结构管理在 carry/JSON 域/「+ 同级」,分组头是兑现不了的隐喻

### D6 前端 bracket 寻址(对齐 gimbal 语义)

jsonpath.ts 重写 segment 解析:`'a[0].b'` → `['a', 0, 'b']`;
setByPath 中间节点按下一 segment 类型建容器(string → dict,number → list),数组越界 pad null —
与 gimbal `_set_at`(L456-465)逐字对齐。getByPath 越界/缺容器 → undefined(控件显 default/空,不炸)。

### D7 默认值:展示不落库

- `deepDefaults` 跳过非平铺 path → 新建步骤 body 干净,无幻影骨架
- 控件内 default/example 仍经 getValue 兜底**展示**(placeholder/初显),用户真输入才落 body

### D8 容器级剪枝(清空语义)

> 清空深层控件 → 只删叶子键 → 若整个根容器子树再无任何非空值 → 删根键,carry 整包注入资格恢复。

- **禁止删中间空元素**:删 `[1]` 会使 `[2]` 洗成 `[1]`,后续所有行 path 静默漂移
- 中间态(`[null, {}]`)保留:说明还有别的行占容器,恰恰不该恢复 carry
- 平铺字段维持 clear='' 不变(差异是有意的:防幻影容器挡 carry)

### D9 深层派生行 + 「+ 同级」(批二,纯前端)

- **深层其他字段** = body 派生行:扫描 body 容器根下的深层叶子,未被任何 binding path 精确覆盖 →
  自动成行(标签 = 相对路径 mono);行是 body 纯投影,持久化零成本(body 即状态)
- 派生行现场合成 IOFieldBinding → ☰ 菜单/策略角标/注入只读态按 path 匹配,全部复用
- **「+ 同级」**:`setByPath(body, '容器[N+1].<同字段>', '')` → 派生行即现;
  **carry 容器上不显示该按钮**(compose 时加同级 = 接管整包,按钮出现即合法优于出现即警告)
- 删除同 D8 剪枝规则

### D10 运行时边界(诚实声明)

- 已声明下标照常注入;运行时员额不足 → assign 落空按 onFailure 降级(pad 语义仅对 set 生效)
- 「每个元素都注入」= 通配/循环,运行时拒写,未来特性,不在本设计
- 响应侧(从不定长数组提取)无此问题:extract 读路径原生支持通配

### D11 export 视图(platform.py)

- `_render_request_view` binding 补全从 `full_body[f.name]` 平铺写改为 **path 寻址写值**(深层值落嵌套)
- `fields_meta[f.name]` 键控保留(name 唯一后安全,条目自带 path)
- `_merge_carry_literal` 不动(carry 已限平铺/dot)

### D12 不存 parent 字段;投影派生 + 声明顺序约定

- parent 双路可推导:path 自身前缀结构 + 清单内最长已声明祖先(D3 同一份包含代码)
- 存储字段 = 反规范化 = 漂移风险 + 校验面膨胀 + 破坏 wire 同形;否决
- declarations.ts(前端唯一投影入口)派生 `parentPath` 随 IOFieldBinding 下发
- spec 约定:**容器先声明,叶子紧随** — 邻接即免费的层级表达(dispatch 文件 90 条随机交错才是
  可读性主因);配可选排序 helper,不建 lint 机器

## 4. 影响面确认(name 消费点全景)

| 消费点 | 用法 | 结论 |
|--------|------|------|
| io_spec `_validate_path_name_enum` | name==末段校验 | **废除**(意识性 re-baseline test_schema_endpoint.py §875-949) |
| io_spec `_check_declarations` | path 唯一 | +name 唯一、+D2 形态、+D3 四格 |
| plate export/platform.py | fields_meta[name] / full_body[name] | 前者保留;后者改 path 寻址(D11) |
| backend endpoint_catalog.py | /full 透传 declarations | 零影响 |
| backend run_materialize / carry_injection | carry fill-missing、{path:type} | 零影响(carry 已限平铺/dot) |
| plate service/field_defaults.py | name 作建议标签 | 零影响(别名友好) |
| 前端 declarations.ts | 投影 | +parentPath 派生(D12) |
| 前端 jsonpath.ts | path 寻址 | +bracket(D6)、+剪枝原语(D8) |
| 前端 FieldForm | 值读写 by path;角标/菜单/注入态 by name 键控 | name 唯一后键控安全;roots 根段 bracket 归一;+角标/警告行 |
| 前端 useFieldDescriptions.ts | `[f.name, f]` Map | name 唯一后安全 |
| 前端 csv-dataset.ts | case 名,非字段 | 零影响 |
| types/plate.ts | IOFieldBinding 注释「与 name 末段一致」×2 | 注释更新(L65/L91) |
| gimbal 运行时 | jsonpath get/set/assign | 零改动 |

## 5. 架构不变量(不动承重墙)

1. B7 通道闭合 {binding, carry}(请求面)不变 — 只补 path 形态边界
2. 三态治理(binding|carry|Type C)不变 — 判定粒度从顶层键细化到 path 匹配
3. declarations 单一真源、wire 同形不变 — 不加任何存储字段
4. carry 整容器传递 + fill-missing(body 显式值优先)语义不变 — 钉死为容器级
5. 同 path 跨通道互斥不变
6. declare() 糖不变(只产平铺 name=key 条目;深层仍手写 DeclarationEntry)

## 6. 兼容性

- 存量契约全平铺:新校验(D1 唯一/D2 形态/D3 四格)对全平铺清单**等价 no-op**;golden 快照不变
- 唯一意识性变更:test_schema_endpoint.py 中「name≠末段必拒」断言翻转为接受(V2 §2.3/§2.4 文档依据
  由本 spec D1 继任)
- 前端存量行为:平铺字段 get/set/角标/菜单全链不变(jsonpath 重写对 dot-only path 逐语义兼容)

## 7. 测试策略

- **plate**(tests/plate/test_deep_path_declarations.py 新):别名通过(dispatch 四条原样)、
  name 撞车拒、carry 深层拒、binding 通配拒、四格×4、name 非标识符拒、存量 endpoint 全量扫描仍绿
- **前端**:jsonpath.test.ts 补 bracket 读/写/pad/剪枝;FieldForm 深层行渲染/角标/警告行/清空剪枝;
  Canvas 注入态×深层 path;declarations parentPath 派生
- **端到端**:dispatch 端点声明落地后 plate 8765 /full 目检 + vitest 全量 + vue-tsc

## 8. 批次划分

- **批一(契约 + 渲染主链)**:plate io_spec 校验重构 → re-baseline 旧测试 → platform.py path 寻址 →
  前端 jsonpath bracket → declarations parentPath + 角标 + roots 归一 → FieldForm 深层读写/剪枝/警告行 →
  dispatch 端点落地(用户 WIP 协调)
- **批二(纯前端,plate 零改)**:深层派生行 → 「+ 同级」按钮

实现计划:docs/superpowers/plans/2026-09-03-deep-path-declarations.md
