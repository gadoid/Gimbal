# 目录外请求字段提升进 form 树 — 设计 spec

日期:2026-09-14
分支:feat/dataset-driven-refactor-phase2
前置:字段状态链(2026-09-05 §3)+ 字段找回(2026-09-07 §2)已实施

## 1. 问题

步骤编辑的字段状态功能(field_states)目前只能操作**目录内**条目:

- 三层封死在目录宇宙:行尾下拉/搜索框经 `cascadeIncrements` 的 `locate()`
  ([declarations.ts:300-312](../../../src/gimbal-platform/frontend/src/utils/declarations.ts#L300-L312))
  目录外 path 返回空批;`searchCorpus` 只遍历目录 declarations;后端
  `validate_field_states` 对目录外 path 报 `stale_path` 警告
  ([field_state_resolution.py:195-201](../../../src/gimbal-platform/backend/app/services/field_state_resolution.py#L195-L201))。
- 目录外 body 残留(`$.extra` 等,由「其他字段」区承载)只能以 textarea/文本
  行编辑,**无法进 form 树**:拿不到变量引用(`${var.x}` 插入)、树形结构编辑、
  字段状态切换、找回归宿。
- 连带真 bug:plate 导出 `_render_request_view`
  ([platform.py:258-355](../../../src/gimbal-plate/gimbal_plate/export/platform.py#L258-L355))
  在 ep 存在时 `full_body` 只并入 carry/声明面 —— **顶层目录外键被静默丢弃**
  (保存 → 导出 → 重载丢数据;详见 §6 丢失面分析)。

用户实际场景:不同被测场景需要配置不同参数组合,目录未声明的请求字段
(接口新增参数、可选扩展键)也要能以 form 树的完整编辑面配置。

## 2. 用户裁定(2026-09-13 讨论)

1. **提升目标态只出 form/collapse,不设 carry**。carry 面只遍历目录
   (carryPaths / carry_face),目录外结构上不可能 carry,与提升无冲突。
2. **修 plate 导出丢目录外键问题**(platform.py `_render_request_view`)。
   plate 冻结纪律由本裁定显式豁免,**仅此一处**;plate 套件其余不动。
3. 只考虑**请求字段**(排除 headers 与响应字段)。
4. 提升后字段出现在 form 树,让用户灵活配置。

## 3. 核心语义:提升 = 渲染归属迁移,不是数据迁移

目录外 path 的值**本来就在 body**(extras 区 `setExtra` → `setByPath` →
`update:body` → Canvas 写 `currentStep.request.body`,注入面早已覆盖目录外
path)。「提升」做的事:

> 把目录外 body path 写进 `step.field_states`(值 ∈ {form, collapse}),
> 该 path 从「其他字段」残留行消失、在 form 树以合成子树出现。

值不搬家、不复制;field_states 是**渲染意图**,与值通路
(`setValue`/`setExtra` → body)分离的既有分离原则(2026-09-05 §3.1)不变。

## 4. 前端设计

### 4.1 单点拼接:`effectiveDecls`(本 spec 的架构核心)

不逐个改 `buildTree`/`searchCorpus`/`cascadeIncrements`/`extraBodyPaths` 的
签名与内部逻辑,而是新增一个纯函数:

```ts
/** declarations.ts 新增 */
export function promotedDecls(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates: Record<string, string> | null | undefined,
  body: unknown,
): DeclarationEntryView[]
```

产出**合成目录条目树**,拼在目录之后:

```ts
// CaseComposerCanvas.vue
const effectiveDecls = computed(() => [
  ...(stepDecls(step) ?? []),
  ...promotedDecls(stepDecls(step), step.field_states, step.request?.body),
])
```

下游消费点全部换喂 `effectiveDecls`(Canvas 内 4 处:
`fieldBindings`/`requestNodes`/`fieldSearchCorpus`/`requestExtras`,
及 `onFieldState` → `cascadeIncrements` 一处)。

拼接后各函数**天然**获得提升语义(这就是选单点拼接而非逐函数加参的原因):

| 函数 | 拼接后行为 | 需要的额外动作 |
|---|---|---|
| `catalogPaths` | 合成条目 path 进宇宙 → `extraBodyPaths` 残留行自动消失 | 无 |
| `extraBodyPaths` | 合成容器带 children → 走「已覆盖容器下钻」分支,内部残留照常成行 | 无 |
| `searchCorpus` | 提升字段可搜、可切态 | 无 |
| `cascadeIncrements` | `locate()` 找到合成条目,form/collapse 切换可用 | carry 目标门禁(§4.4) |
| `buildTree` | 合成节点按 body 值实例化渲染 | 无 |

### 4.2 `promotedDecls` 的合成规则

输入筛选:遍历 `field_states`,取解析态 ∈ {form, collapse} **且**
`toTemplatePath(path)` ∉ `catalogPaths(decls)` 的条目 —— 即「已提升」的
目录外 path 集合 `P`。

结构折叠(深层 path 需要父容器):把 `P` 按 path 段折叠成前缀树。
`$.a.b` + `$.a.c` → 合成 object `$.a` + children `[b, c]`;`$.a` 与
`$.a.b` 同时提升 → `$.a` 是提升根,`$.a.b` 是其子孙(不再单独合成顶层)。

条目合成(`DeclarationEntryView` 形状,值取自 body,`getByPath`):

- `path`:field_states 里的 path(模板形态)
- `name`:末段(`$.a.b` → `b`;顶层 `$.extra` → `extra`)
- `type`:按 body 值推断 —— object → `object`、array → `array`、
  number/boolean → 同名、其余 → `string`;**body 无值**(schema 契约差集行
  提升场景)→ `string`
- `state`:条目自带 `'form'`(让 `resolveState` 的增量链在 buildTree 内
  正常解析;真实意图本来就在 field_states 里)
- `children`:仅 object 折叠出 children(按 body 实际键一层展开;深层递归
  —— body 有值就照实展开,array 行组同 `buildTree` 既有实例化语义交由
  buildTree/buildNode 本体处理);array/叶子无 children
- `required: false`、`description: ''`、`enum: null`、`ui_kind` 按类型
  (`text`/`number`/`boolean`)、`source_kind: 'independent'`、
  `value_source: null`、`default`/`example: null`

实现复用:叶子/合成行实例化与 `synthRowNode`
([declarations.ts:560-622](../../../src/gimbal-platform/frontend/src/utils/declarations.ts#L560-L622))
同款值类型推断,不另起一套。

### 4.3 「其他字段」区加提升入口(FieldForm.vue)

extras 区残留行(`source: 'body'`,目录外实有)加「提升」按钮
([FieldForm.vue:836-903](../../../src/gimbal-platform/frontend/src/components/composer/FieldForm.vue#L836-L903)
extras 模板区 + `ExtraRowView`):

- 点击 → `emit('promote', row.path)` → Canvas `onFieldState(path, 'form')`
  (走既有 `applyFieldStates` 批量通路,校验/回滚语义白拿)
- schema 契约差集行(`source: 'schema'`,body 无值)同样可提升:
  `promotedDecls` 对无值 path 也产条目(§4.2),树内渲染空值节点,
  placeholder 走 default(若有)
- 提升后残留行从 extras 消失(universe 并入,§4.1),字段出现在树内

降级(撤销提升):树内合成节点行尾 FieldStateSelect ↺ 重置
(清 field_states 增量)→ 回到 extras 残留行。**值不动**,双向可逆。

### 4.4 carry 门禁(裁定 1)

- 合成条目在树内的 FieldStateSelect 下拉**不提供 carry 选项**
  (FieldStateSelect 加 `noCarry?: boolean` prop;FieldForm 对合成节点
  —— 经 `promotedDecls` 产出的节点需可识别 —— 传入)
- `cascadeIncrements` 不为目录外 path 产 carry 增量:目标态 carry 且
  locate 命中的是合成条目 → 空批(防御纵深;UI 门禁是第一道)
- 识别方式:`buildTree` 节点无「合成」标记 —— 在 `promotedDecls` 产出的
  条目 `description` 置空已不可辨。方案:合成条目 `name` 不变,但
  FieldForm 需要 propagate 标记。**裁定:Canvas 把 promoted path 集合
  (`promotedPaths: Set<string>`)作为 prop 传给 FieldForm,FieldForm 行尾
  菜单据此门禁** —— 不污染 declarations 数据形状,不靠启发式识别。

### 4.5 前端不改的面(显式排除)

- **注入面**:extras `setExtra` 与树 `setValue` 同落点(copyBody →
  setByPath → body),提升前后注入通路不变
- **carry 面**:`carryPaths`/`carry_face` 只遍历目录,合成条目不在
  (拼接只发生在 Canvas 的 effectiveDecls,后端/值表消费真源目录)
- **响应契约面**(`contractTree`/`formFace`):响应面无视 state,目录外
  契约差集已有 unboundFields 行,不进本变更
- **导出/持久化 shape**:field_states 本就存目录外 path
  (validate 只警告不拒),无需 schema 改动

## 5. 后端设计(backend)

### 5.1 `validate_field_states` stale 判定放宽

[endpoint_catalog.py:37-40](../../../src/gimbal-platform/backend/app/routers/endpoint_catalog.py#L37-L40)
`FieldStatesValidateRequest` 加可选 `body`:

```python
body: dict[str, Any] | None = None   # step.request.body(实有键参照,stale 判定用)
```

`validate_field_states(declarations, field_states, body=None)`(新第三参):
`stale_path` 判定从「path ∉ 目录宇宙」改为:

> path ∉ 目录宇宙 **且** 模板化 path 不在 body 实例路径集合 → stale 警告;
> 目录外但 body 实有(提升字段)→ 放行,不警告。

body 实例路径集合:递归展开 body,实例路径 `$.a[0].b` 模板化
(剥 `[i]`,与前端 `toTemplatePath` 同式;后端写同款小 helper,不复用
jsonpath 模块的实例寻址 —— 这里只要路径形态集合)。

前端 `applyFieldStates` 调 `validateEndpointFieldStates` 时带上
`step.request.body`([api/endpoint-catalog 侧函数加参](../../../src/gimbal-platform/frontend/src/api/));旧调用不传 body → 行为不变(向后兼容)。

### 5.2 其余不动

- `resolve_state`/`carry_face`/`composite_states`:解析链对目录外 path
  本就读穿(field_states 命中即返),无需改
- 保存链路门禁:stale 是 warning 不是 error,提升字段永不被拒

## 6. plate 导出修复(冻结豁免一处)

### 丢失面分析

`_render_request_view` ep 存在分支的三步:

1. carry/有 children 容器:`_merge_carry_literal(e.path, body, full_body)`
   —— body 字面量整块并入(深层兄弟键**保住**)
2. fields_meta 登记(不碰 body)
3. 声明叶子补全:`_get_by_path(body)` → default → example → None

**顶层目录外键**(`$.extra`,无任何声明覆盖)三步全不沾 → 丢。
深层残留仅在「父容器无 children 声明」时丢 —— 该形态容器在步骤 3 按
`_get_by_path` 拿到整容器值写入,实际也保住。故丢失面收敛为:
**目录顶层未声明的 body 键(含其整个子树)**。

### 修法

ep 存在分支末尾(步骤 3 之后)补一轮顶层差集并入:

```python
# 4) 目录外顶层键整块并入(2026-09-14 提升配套):目录只覆盖声明面,
#    body 顶层未声明键(含子树)三步全不沾会被静默丢弃。整块 merge
#    保住 platform→gimbal 往返子集契约;与步骤 1 同式(_merge_carry_literal
#    对顶层平铺路径即整值拷贝)。
declared_roots = {_path_segs(e.path)[0] for e in iter_declarations(decls)
                  if _path_segs(e.path)}
for k, v in body.items():
    if k not in declared_roots:
        full_body[k] = v
```

(`_path_segs` 首段可能是 int 下标 —— 整 body 为数组时 `body.items()`
不可用;该形态下 body 是 list,`dict(body)` 分支语义本就不涉及,守卫按
`isinstance(body, dict)` 包住即可。)

验证:回归测试写进 [tests/plate/test_v3_export_platform.py](../../../../tests/plate/test_v3_export_platform.py)
(`_render_request_view` 的既有测试文件),验证只跑该文件
(`pytest tests/plate/test_v3_export_platform.py`),plate 套件其余文件与
测试零触碰 —— 与用户裁定的豁免口径一致(只动 platform.py 一处实现 +
其回归测试)。

## 7. 数据流总览(提升后)

```
用户在 extras 区点「提升」($.extra)
  → FieldForm emit('promote', '$.extra')
  → Canvas onFieldState('$.extra', 'form')
  → applyFieldStates({'$.extra': 'form'})           # 既有通路,校验+回滚白拿
      ↓ validate(body 随行)                          # §5.1,不报 stale
  → step.field_states['$.extra'] = 'form'
      ↓ 响应式
  → effectiveDecls 重算:promotedDecls 产合成条目
  → requestNodes 含 $.extra 子树(值照读 body)
  → requestExtras 不再含 $.extra(universe 并入)
  → 树内行尾可切 form/collapse(无 carry);↺ 重置回 extras
  → 保存 → 导出:_render_request_view 步骤 4 保住 $.extra(§6)
```

## 8. 测试策略(TDD)

前端(vitest):

- `promotedDecls`:提升根/object 折叠 children/深层前缀树合并/`$.a` 与
  `$.a.b` 同提升/body 无值(schema 行)/值类型推断/非提升态(carry 值、
  目录内 path)零产出 —— 约 7 例
- `extraBodyPaths` + promotedDecls 组合:已提升根残留行消失、容器内部
  残留照常成行
- `cascadeIncrements`:合成条目 form↔collapse 切换、carry 目标空批
- FieldForm:extras 行提升按钮 emit、树内合成节点无 carry 选项
- Canvas 集成:提升 → 树出现/extras 消失/field_states 落键/↺ 回退

后端(pytest):

- `validate_field_states` 三参:目录外+body 实有 → 无 stale;目录外+无
  body → stale 不变;不传 body(旧调用)→ 行为不变
- 路由:`FieldStatesValidateRequest.body` 透传

plate(豁免一处,只跑 test_v3_export_platform.py):

- `_render_request_view` 顶层目录外键保留(round-trip 断言)、声明根不
  双写、body 非对象(list)守卫

## 9. 边界与风险

- **双重渲染**:已提升根必须在 extraBodyPaths 消失 —— catalogPaths 并入
  是结构性保证(同一路径两处来源互斥),测试钉死
- **提升根删除值**:树内清空叶子(深层清空 D8 剪枝)可能剪掉整个提升
  容器 → body 无值但 field_states 仍留增量 → promotedDecls 对无值 path
  仍产条目(空树),用户可 ↺ 或重新填值。**不自动清 field_states**
  (显式增量是漂移保护凭据,§3.3 语义)
- **目录后来声明了同名 path**(plate 目录更新):合成条目与目录条目同
  path —— 拼接序目录在前,buildTree 双节点渲染重复。防御:promotedDecls
  筛选时对目录宇宙做**子串包含**判定(path ∈ 目录或目录条目是其祖先/
  子孙 → 不合成,目录赢)。测试钉死
- **carry 祖先下的提升**:`$.supplier` 是 carry 容器(目录内),其子键
  body 残留会被 carry 面吸收(extraBodyPaths 的 underCarry)→ 不会出现在
  extras → 无从提升。结构上无冲突,文档化即可
