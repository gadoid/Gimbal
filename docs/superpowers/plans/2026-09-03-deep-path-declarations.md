# 深层路径声明与 name↔path 解绑 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 深层嵌套叶子可声明(binding)、可渲染(表单行)、可注入 — name↔path 解绑 + 三处视图补齐,执行引擎零改动。

**Architecture:** plate 契约层废 name==末段规则,换成 name 全清单唯一 + 通道 path 形态边界 + 包含关系四格;前端 jsonpath 补 bracket 寻址(对齐 gimbal `_set_at` 语义);渲染无层级平铺 + path 角标 + parentPath 投影派生;清空走容器级剪枝。批二纯前端:body 派生深层行 + 「+ 同级」。

**Tech Stack:** pydantic(plate)/ pytest / Vue3 + vitest + vue-tsc

**Spec:** docs/superpowers/specs/2026-09-03-deep-path-declarations-design.md(决策编号 D1-D12 下文引用)

## Global Constraints

- `probe_ui.js` 永不触碰
- 用户 WIP 文件不碰:工作树中 order_entrust_order_dispatch.py(Task 7 落地前须征得用户同意)、
  order_entrust_order_add.py、gaegea.json、test-report.html、carry 批次文件均属用户未提交 WIP
- 选择性暂存:只 `git add <本任务显式文件>`,绝不 `git add -A`
- 意识性 re-baseline:改既有断言必须在 commit message 与测试注释中声明依据(Task 2),不许静默改
- plate 8765 常驻普通模式;`--reload` 只在用户真终端
- 后台 Bash 必须 cd 进命令本身;vue-tsc 必须 `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vue-tsc --noEmit`
- commit 中文 + 结尾 `Co-Authored-By: Claude <noreply@anthropic.com>`
- 运行器:plate 测试 `cd /d/Gimbal/Gimbal && python -m pytest tests/plate -q`;
  前端 `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run`

---

## 批一(契约 + 渲染主链)

### Task 1: plate 契约校验重构(D1/D2/D3)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/utils/path.py`(追加 `parse_nodes`)
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`
- Test: `tests/plate/test_deep_path_declarations.py`(新建)

**Interfaces:**
- Produces: `path.parse_nodes(value: str) -> list[PathNode] | None`(非法/空 → None);
  DeclarationEntry 校验新规则(name 标识符、name 唯一、carry 平铺、binding 具体、包含四格)

- [ ] **Step 1: 写失败测试**(新建 `tests/plate/test_deep_path_declarations.py`)

```python
"""深层路径声明(D1-D3):name 别名制、通道形态边界、包含四格。
设计依据:docs/superpowers/specs/2026-09-03-deep-path-declarations-design.md"""
import pytest
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry, RequestSpec

_SCHEMA = {"type": "object", "properties": {}}

def _build(*entries):
    return RequestSpec(body_type="json", schema=_SCHEMA,
                       declarations=list(entries))

def _decl(**kw):
    base = dict(name="x", path="$.x", channel="binding")
    base.update(kw)
    return DeclarationEntry(**base)

# ── D1 别名制 ─────────────────────────────────────────────
def test_alias_name_accepted():
    """dispatch 原样案例:name≠末段 通过(name=显示别名,path=寻址真源)。"""
    _build(
        _decl(name="supplier_id", path="$.supplier[0].order_supplier_id"),
        _decl(name="order_id_relate_supplier", path="$.supplier[0].order_id"),
        _decl(name="order_id", path="$.order_id"),
    )

def test_duplicate_name_rejected():
    with pytest.raises(ValueError, match="重复 name"):
        _build(_decl(name="order_id", path="$.order_id"),
               _decl(name="order_id", path="$.supplier[0].order_id"))

def test_non_identifier_name_rejected():
    with pytest.raises(ValueError, match="标识符"):
        _decl(name="订单ID", path="$.order_id")

# ── D2 通道形态 ───────────────────────────────────────────
def test_carry_deep_index_rejected():
    with pytest.raises(ValueError, match="carry 通道 path"):
        _decl(name="x", path="$.supplier[0].order_supplier_id",
              channel="carry", type="string")

def test_carry_dot_nested_accepted():
    _decl(name="b", path="$.a.b", channel="carry", type="string")

def test_binding_wildcard_rejected():
    with pytest.raises(ValueError, match="具体路径"):
        _decl(name="sku", path="$.supplier[*].order_supplier_id")

def test_binding_deep_index_accepted():
    _decl(name="sku0", path="$.supplier[0].order_supplier_id")

# ── D3 包含四格 ───────────────────────────────────────────
def test_carry_contains_binding_ok():
    """dispatch 主案例:carry 容器 + binding 深层叶子 = 分层覆写。"""
    _build(_decl(name="supplier", path="$.supplier", channel="carry", type="array"),
           _decl(name="supplier_id", path="$.supplier[0].order_supplier_id"))

def test_carry_contains_carry_rejected():
    with pytest.raises(ValueError, match="carry 声明不允许嵌套"):
        _build(_decl(name="supplier", path="$.supplier", channel="carry", type="array"),
               _decl(name="leaf", path="$.supplier.x", channel="carry", type="string"))

def test_binding_contains_binding_ok():
    _build(_decl(name="cfg", path="$.cfg", ui_kind="json"),
           _decl(name="timeout", path="$.cfg.timeout"))

def test_binding_contains_carry_rejected():
    with pytest.raises(ValueError, match="binding 容器内不允许 carry"):
        _build(_decl(name="cfg", path="$.cfg", ui_kind="json"),
               _decl(name="owner", path="$.cfg.owner", channel="carry", type="string"))
```

- [ ] **Step 2: 跑测试确认失败**(`python -m pytest tests/plate/test_deep_path_declarations.py -q`,预期:别名/深层数条 FAIL,规则类 FAIL)

- [ ] **Step 3: path.py 追加 `parse_nodes`**

```python
def parse_nodes(value: str) -> "list[_jp.PathNode] | None":
    """合法 path → 节点序列(非法/空/非字符串 → None)。

    包含判定(io_spec D3)与通道形态判定(D2)的公共入口。
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return _jp._parse(value)
    except _jp.JsonPathError:
        return None
```

- [ ] **Step 4: io_spec.py 三处修改**

① `_validate_path_name_enum`:删除 name==末段 检查块(L40-44 `seg = ... if seg is not None and name != seg: raise`),docstring 改为「path 合法性/归一化 + enum 一致性(name↔path 解绑见 2026-09-03 spec D1)」,返回 `norm` 逻辑保留;函数签名 `name` 参数保留(向后兼容调用点)但不再参与校验。
② `DeclarationEntry._validate_entry` 开头加 name 标识符校验(需 `import re`,模块级 `_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")`):

```python
        if not _NAME_RE.match(self.name):
            raise ValueError(
                f"DeclarationEntry.name={self.name!r} 须为 ASCII 标识符"
                f"([A-Za-z_][A-Za-z0-9_]*,作显示别名与前端键)"
            )
```

③ `_check_declarations` 在既有 path 唯一检查后追加:

```python
    # D1 name 全清单唯一:name 是前端键控/显示别名,撞名即结构性冲突
    seen_names: set[str] = set()
    dup_names: list[str] = []
    for e in declarations:
        if e.name in seen_names and e.name not in dup_names:
            dup_names.append(e.name)
        seen_names.add(e.name)
    if dup_names:
        raise ValueError(f"{owner} declarations 内重复 name: {dup_names}")
    # D2 通道形态:carry 限平铺/dot(整容器传递);binding 限具体路径(拒通配/filter/递归)
    for e in declarations:
        nodes = _path.parse_nodes(e.path)
        if nodes is None:
            continue  # 条目级校验已拒,防御
        if e.channel == "carry" and any(n.kind.name != "FIELD" for n in nodes):
            raise ValueError(
                f"{owner} carry 通道 path 限平铺/dot 嵌套(整容器传递,值表存容器 JSON):{e.path!r}"
            )
        if e.channel == "binding" and any(
                n.kind.name not in ("FIELD", "INDEX") for n in nodes):
            raise ValueError(
                f"{owner} binding 通道 path 须为具体路径(FIELD/INDEX,拒通配):{e.path!r}"
            )
    # D3 包含四格:carry⊃binding ✓(分层覆写)/ carry⊃carry ✗(一树二主)/
    #             binding⊃binding ✓(同归表单)/ binding⊃carry ✗(双所有者)
    parsed = [(e, _path.parse_nodes(e.path)) for e in declarations]
    for outer, onodes in parsed:
        if onodes is None:
            continue
        for inner, inodes in parsed:
            if outer is inner or inodes is None or len(onodes) >= len(inodes):
                continue
            if all(a.kind == b.kind and a.value == b.value
                   for a, b in zip(onodes, inodes)):
                if outer.channel == "carry" and inner.channel == "carry":
                    raise ValueError(
                        f"{owner} carry 声明不允许嵌套(一树二主):"
                        f"{outer.path!r} ⊃ {inner.path!r}"
                    )
                if outer.channel == "binding" and inner.channel == "carry":
                    raise ValueError(
                        f"{owner} binding 容器内不允许 carry 声明(容器归表单,叶子归值表):"
                        f"{outer.path!r} ⊃ {inner.path!r}"
                    )
```

- [ ] **Step 5: 跑新测试通过 + 全量 plate 测试**(Task 2 的 re-baseline 除外,若旧 name 规则测试红属预期,留 Task 2)
- [ ] **Step 6: Commit** `feat(plate): 声明校验 D1-D3 — name 别名制+唯一、通道形态边界、包含四格`

### Task 2: 意识性 re-baseline 旧 name 规则测试

**Files:**
- Modify: `tests/plate/test_schema_endpoint.py`(L912-960 区域)

- [ ] **Step 1: 定位并翻转断言**:该区域三个测试点 —「嵌套 path name=c 必须通过」(保留)、
  「name=b 必须拒」(L940 区域)、「name 与最浅层末段不一致必拒」(L949 区域)。后两处从
  `pytest.raises(ValueError)` 翻转为构造通过,并在测试注释加:

```python
        # 意识性 re-baseline(2026-09-03 D1):name↔path 解绑,name 为显示别名,
        # 旧 V2 §2.3/§2.4 "name=末段" 规则由 name 全清单唯一校验继任。
```

- [ ] **Step 2: 全量 `python -m pytest tests/plate -q` 绿**
- [ ] **Step 3: Commit** `test(plate): 意识性 re-baseline name==末段断言 — D1 别名制继任`

### Task 3: plate export binding 补全按 path 寻址(D11)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/export/platform.py`(`_render_request_view`)
- Test: 既有 platform export 测试文件(执行时 Glob `tests/plate/test_*platform*` 定位;无则新建)

- [ ] **Step 1: 写失败测试**:构造带深层 binding 声明的 EndpointSpec + step body,断言导出
  `full_body` 中值为嵌套形态(`{"supplier": [{"order_supplier_id": "x"}]}`)而非顶层平键
  `{"supplier_id": "x"}`;深层 binding 无值时 **不落 None 骨架**(平铺 binding 维持 None 占位现行为);
  `fields_meta` 仍按 name 键控且条目带 path。
- [ ] **Step 2: 实现**:platform.py 加模块级辅助(需 `import re`):

```python
_MISSING = object()


def _path_segs(path: str) -> list[Any]:
    """'$.a[0].b' → ['a', 0, 'b'](FIELD/INDEX 段;binding 限具体路径后无通配)。"""
    segs: list[Any] = []
    for m in re.finditer(r"([^[\].]+)|\[(\d+)\]", path.lstrip("$.")):
        segs.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
    return segs


def _get_by_path(data: Any, segs: list[Any]) -> Any:
    cur = data
    for seg in segs:
        if isinstance(seg, int):
            if not isinstance(cur, list) or seg >= len(cur):
                return _MISSING
            cur = cur[seg]
        else:
            if not isinstance(cur, dict) or seg not in cur:
                return _MISSING
            cur = cur[seg]
    return cur


def _set_by_path(container: Any, segs: list[Any], value: Any) -> Any:
    """按段写值,中间节点自动创建(FIELD→dict/INDEX→list+pad None),对齐 gimbal _set_at。"""
    if not segs:
        return value
    seg, rest = segs[0], segs[1:]
    if isinstance(seg, int):
        if not isinstance(container, list):
            container = []
        while len(container) <= seg:
            container.append(None)
        container[seg] = _set_by_path(container[seg], rest, value)
        return container
    if not isinstance(container, dict):
        container = {}
    container[seg] = _set_by_path(container.get(seg), rest, value)
    return container
```

`_render_request_view` binding 循环改为:

```python
        for f in (e for e in ep.request.declarations if e.channel == "binding"):
            fields_meta[f.name] = f.model_dump(mode="json", exclude_none=True)
            segs = _path_segs(f.path)
            deep = len(segs) > 1 or isinstance(segs[0], int)
            value = _get_by_path(body, segs)
            if value is _MISSING:
                if f.default is not None:
                    value = f.default
                elif f.example is not None:
                    value = f.example
                else:
                    value = None
            if value is None and deep:
                continue  # D7:深层无值不落 None 骨架(防挡 carry 容器注入)
            if deep or value is not _MISSING:
                _set_by_path(full_body, segs, value)
```

(平铺路径 `_set_by_path(full_body, ['x'], v)` 与旧 `full_body[f.name] = v` 等价;carry 面逻辑不动。)
- [ ] **Step 3: plate 全量绿** → Commit `feat(plate): export binding 补全按 path 寻址 — 深层值落嵌套`

### Task 4: 前端 jsonpath bracket 寻址 + 容器级剪枝(D6/D7/D8)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/jsonpath.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/jsonpath.test.ts`

- [ ] **Step 1: 失败测试**(追加用例,全部具体断言):

```ts
// D6 bracket 读:容器缺失/下标越界 → undefined 不炸
getByPath({}, 'supplier[0].order_id') === undefined
getByPath({ supplier: [null, { order_id: 'x' }] }, 'supplier[1].order_id') === 'x'
// D6 bracket 写:自动建链 + pad null(对齐 gimbal _set_at)
setByPath 写 'supplier[2].order_id' = 'x' 后 body === { supplier: [null, null, { order_id: 'x' }] }
// D7 deepDefaults:非平铺 path 跳过(default 不落库)
deepDefaults([{ path: '$.supplier[0].x', default: 'd', example: null },
              { path: '$.flat', default: 'f', example: null }]) === { flat: 'f' }
// D8 pruneByPath:整树空 → 根键消失(恢复 carry 资格)
pruneByPath({ supplier: [{ order_id: 'x' }] }, 'supplier[0].order_id') 后 === {}
// D8:兄弟占容器 → 容器保留
pruneByPath({ supplier: [{ a: 1, order_id: 'x' }] }, 'supplier[0].order_id') 后 supplier 仍在且 [0].a === 1
// D8:中间空元素保留(索引不漂移)
pruneByPath({ supplier: [{ order_id: 'x' }, { b: 1 }] }, 'supplier[0].order_id')
  后 === { supplier: [null, { b: 1 }] }   // [0] 置 null,不 splice 洗位
```

- [ ] **Step 2: 重写 jsonpath.ts**(保持既有导出名,新增 `pruneByPath`;文件头能力边界注释更新为
  「支持 `$.a.b` 与 `$.a[0].b`(FIELD/INDEX);通配/过滤器/递归仍不支持,与 Python 侧写路径边界一致」):

```ts
/** 'a[0].b' → ['a', 0, 'b'](下标转 number;容器按下一 segment 类型创建) */
function parseSegments(rel: string): Array<string | number> {
  const segs: Array<string | number> = []
  for (const m of rel.matchAll(/([^[\].]+)|\[(\d+)\]/g)) {
    segs.push(m[1] !== undefined ? m[1] : Number(m[2]))
  }
  return segs
}

export function getByPath(obj: any, path: string): any {
  if (!obj || !path) return undefined
  let cur = obj
  for (const seg of parseSegments(path.replace(/^\$\./, ''))) {
    if (cur === null || cur === undefined) return undefined
    cur = typeof seg === 'number'
      ? (Array.isArray(cur) ? cur[seg] : undefined)
      : cur[seg]
  }
  return cur
}

export function setByPath(obj: any, path: string, value: any): void {
  if (!obj || !path) return
  const segs = parseSegments(path.replace(/^\$\./, ''))
  let cur = obj
  for (let i = 0; i < segs.length - 1; i++) {
    const seg = segs[i]
    let child = cur[seg]
    if (child === null || child === undefined || typeof child !== 'object') {
      child = typeof segs[i + 1] === 'number' ? [] : {}
      if (typeof seg === 'number') {
        while (cur.length <= seg) cur.push(null)
      }
      cur[seg] = child
    }
    cur = child
  }
  const last = segs[segs.length - 1]
  if (typeof last === 'number') while (cur.length <= last) cur.push(null)
  cur[last] = value
}

/** D8 容器级剪枝:删叶子(FIELD→delete 键/末段 INDEX→置 null,不 splice 防索引漂移);
 *  祖先链因此全空(空 dict/空 list/全 null)→ 连锁删到根键;中间空元素保留。 */
export function pruneByPath(obj: any, path: string): void {
  if (!obj || !path) return
  const segs = parseSegments(path.replace(/^\$\./, ''))
  if (!segs.length) return
  const chain: any[] = [obj]
  for (let i = 0; i < segs.length - 1; i++) chain.push(chain[chain.length - 1]?.[segs[i]])
  const parent = chain[chain.length - 1]
  const last = segs[segs.length - 1]
  if (parent == null || typeof parent !== 'object') return
  if (typeof last === 'number') parent[last] = null
  else delete parent[last]
  const isEmpty = (v: any): boolean =>
    Array.isArray(v) ? v.every((x) => x == null) :
    v && typeof v === 'object' ? Object.keys(v).length === 0 : true
  for (let i = segs.length - 2; i >= 0; i--) {
    if (!isEmpty(chain[i + 1])) break
    const seg = segs[i]
    if (typeof seg === 'number') chain[i][seg] = null
    else delete chain[i][seg]
  }
}
```

`deepDefaults` 循环体加一行(在取 v 之前):`if (/[.[]/.test(rel)) continue`(rel = path 去前缀;
D7 深层默认只展示不落库,展示由 FieldForm getValue 的 default 兜底承担)。
- [ ] **Step 3**:vitest jsonpath 全绿(含既有 dot-only 用例不回归)→ Commit
  `feat(web): jsonpath bracket 寻址+容器级剪枝 — 对齐 gimbal _set_at 语义`

### Task 5: parentPath 投影 + path 角标 + roots 归一(D5/D12)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`(IOFieldBinding + `parentPath?`/`parentChannel?`;更新 L65/L91 过时注释「与 name 末段一致」→「name 为显示别名,path 为寻址真源(D1)」)
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(角标 + roots)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts`(若无则新建)+ FieldForm 既有测试文件追加

- [ ] **Step 1: declarations.ts 派生逻辑**(字符串前缀判定在归一化形态下可靠:`$.a` 是 `$.a.b`/`$.a[0].c` 祖先,`$.ab` 不是 `$.a` 后代):

```ts
function isAncestor(anc: string, desc: string): boolean {
  if (anc === desc || !desc.startsWith(anc)) return false
  const next = desc[anc.length]
  return next === '.' || next === '['
}

/** D12:最长已声明祖先(无 → null);parentChannel 随源条目。O(n²),声明清单量级无忧。 */
function deriveParent(e: DeclarationEntryView, all: DeclarationEntryView[]): { parentPath: string | null; parentChannel: string | null } {
  let best: DeclarationEntryView | null = null
  for (const o of all) {
    if (o.path !== e.path && isAncestor(o.path, e.path) &&
        (best === null || o.path.length > best.path.length)) best = o
  }
  return best
    ? { parentPath: best.path, parentChannel: best.channel }
    : { parentPath: null, parentChannel: null }
}
```

`toFieldBinding` 签名加 `all` 参数,输出加 `parentPath`/`parentChannel`;`channelFields` 传 `decls`。
- [ ] **Step 2: FieldForm 角标**:`.field-label` 内、非平铺字段(`f.path !== '$.' + f.name`)渲染:

```html
<span class="path-badge" :title="parentTitle(f)">{{ f.path }}</span>
```

```ts
/** 治理标注(D5):carry 上级=值表打底、此处覆写;binding 上级=同容器可 JSON 域整编 */
function parentTitle(f: IOFieldBinding): string {
  if (!f.parentPath) return f.path
  return `${f.path} · 上级 ${f.parentPath}(${f.parentChannel === 'carry' ? 'carry · 值表打底,此处覆写' : 'binding'})`
}
```

样式对齐既有 mono 小字(参考 `.fa-note`/策略角标字号 9-10px,slate 色)。
- [ ] **Step 3: extraRows roots 归一**(L582-584):`b.path.replace(/^\$\./, '').split('.')[0]` →
  `.split(/[.[]]/)[0]`(`'supplier[0]'` 根段归一为 `'supplier'`,容器正确归入 binding 覆盖面)。
- [ ] **Step 4: 测试**:parentPath 派生(嵌套/无祖先/`$.ab` 非 `$.a` 祖先);FieldForm 深层 binding 行
  有 `.path-badge` 且 title 含上级标注,平铺行无;roots 归一后 body 的 `supplier` 容器不再进「其他字段」。
- [ ] **Step 5**:vitest + `npx vue-tsc --noEmit` 绿 → Commit
  `feat(web): 深层字段 path 角标+parentPath 投影 — 治理归属可见`

### Task 6: FieldForm 深层读写行为(清空剪枝 + carry 警告行)(D7/D8)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(传 `carryRoots`)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.test.ts` 追加或新建 `FieldForm.deep.test.ts`

- [ ] **Step 1: setValue 分流**(D8:深层清空=剪枝,平铺维持 ''):

```ts
function setValue(f: IOFieldBinding, val: unknown) {
  if (props.readonly) return
  const next = { ...(props.body || {}) }
  const rel = f.path.replace(/^\$\./, '')
  if (val === '' && /[.[]/.test(rel)) {
    pruneByPath(next, rel)  // D8:清空=删叶子+容器级剪枝(防幻影容器挡 carry)
  } else {
    setByPath(next, rel, val)
  }
  emit('update:body', next)
}
```

- [ ] **Step 2: carry 容器警告行**:FieldForm 新 prop `carryRoots?: string[]`(容器根键集);
  深层字段行(`/[.[]/.test(rel)`)且根键命中时,在 field-desc 位置渲染:

```html
<p v-if="isDeepField(f) && inCarryContainer(f)" class="deep-carry-note">
  上级容器 $.{{ rootOf(f) }} 为 carry 整包传递 — 手填将接管该容器,清空可恢复注入
</p>
```

Canvas 侧(已有 carryPaths 工具):`const carryRoots = computed(() => [...new Set(carryPaths(currentDecls).map((p) => p.replace(/^\$\.?/, '').split(/[.[]]/)[0]))])`,
请求体 FieldForm 传 `:carry-roots="carryRoots"`。
- [ ] **Step 3: 测试**:深层字段清空 → body 容器整体消失;平铺字段清空 → 仍为 '';carry 容器内深层
  字段有警告行、binding 容器内无;深层字段注入 assign 后提示条(既有 injected 机制)与角标共存。
- [ ] **Step 4**:vitest + vue-tsc 绿 → Commit `feat(web): 深层字段清空剪枝+carry 容器接管警告`

### Task 7: dispatch 端点声明落地(⚠ 用户 WIP 文件,动手前征得同意)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_entrust_order_dispatch.py`

- [ ] **Step 1: 与用户确认**该文件当前 WIP 归属(文件含语法错:L51 全角逗号 `，`、L52-54 缺逗号 —
  现在 import 都过不了;git status 显示其为未提交修改)。
- [ ] **Step 2: 修正并按新语义定稿**(容器先声明、叶子紧随,D12 顺序约定):

```python
        DeclarationEntry(name='bl_no', path='$.bl_no', channel='binding', default='Codfish_TEST_001', example='Codfish_TEST_001', ui_kind='text'),
        DeclarationEntry(name='track_bl_no', path='$.track_bl_no', channel='binding', default='Codfish_TEST_001', example='Codfish_TEST_001', ui_kind='text'),
        DeclarationEntry(name='action', path='$.action', channel='binding', default='check', example='submit', description='check[校验]/submit[提交]', ui_kind='text'),
        DeclarationEntry(name='entrust_status', path='$.entrust_status', channel='binding', type='integer', default='', example='1', description='1是检查,2是分发', ui_kind='text'),
        # ── supplier 深层叶子(容器先声明,叶子紧随;$.supplier carry 在下方 carry 段)──
        DeclarationEntry(name='supplier_id', path='$.supplier[0].order_supplier_id', channel='binding', example='', description='服务供应商ID'),
        DeclarationEntry(name='order_id_relate_supplier', path='$.supplier[0].order_id'),
        # 顶层补充(schema 外手写,name 唯一即可)
        DeclarationEntry(name='order_id', path='$.order_id'),
        DeclarationEntry(name='order_no', path='$.order_no'),
```

(default 由 `''` 改 None/省略:D7 深层默认只展示不落库,getValue 兜底展示语义不变。)
- [ ] **Step 3: 验证**:`python -m pytest tests/plate -q` 全绿(含 endpoint 全量扫描);
  plate 8765 `curl /api/endpoint/fin.order_entrust.order_dispatch/full` 目检 declarations。
- [ ] **Step 4**:Commit `feat(plate): order_dispatch 深层声明落地 — supplier[0] 注入叶子`

---

## 批二(纯前端,plate 零改)

### Task 8: 深层派生行(D9)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(extraRows 深层扫描)
- Test: FieldForm.deep.test.ts 追加

- [ ] **Step 1: 失败测试**:body 带 `supplier: [{…}, {order_supplier_id: 'y'}]`、binding 仅覆盖
  `$.supplier[0].order_supplier_id` → 派生行出现且标签为相对路径 `supplier[1].order_supplier_id`;
  未被覆盖叶子可编辑(setByPath 落位)、可删(pruneByPath);派生行有 ☰ 菜单(合成 IOFieldBinding:
  `name=相对路径安全形态(path 派生)、path=完整 $. 路径、ui_kind 按 typeof 值推断`),注入后 assign
  target 为 `$.request_body.supplier[1].order_supplier_id`。
- [ ] **Step 2: 实现**:`deepExtraRows` computed — 取 body 容器根下全部叶子路径(FIELD/INDEX walk),
  排除被任一 binding path 精确覆盖者与 carry 根下叶子(carry 容器不派生行:值归值表);渲染进
  「其他字段」区之上独立「深层字段」小节或 extras 内子组(与既有 extras 样式一致);菜单/事件复用
  既有 FieldActionMenu 接线(合成 binding 直接进现有 handler)。
- [ ] **Step 3**:vitest + vue-tsc 绿 → Commit `feat(web): 深层派生行 — body 投影,菜单/注入复用`

### Task 9: 「+ 同级」按钮(D9)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`
- Test: FieldForm.deep.test.ts 追加

- [ ] **Step 1: 失败测试**:深层 binding 行(如 `$.supplier[0].order_supplier_id`)显示「+ 同级」;
  点击 → body 出现 `supplier[1].order_supplier_id = ''` 且派生行(Task 8)即现;**carry 容器根下的
  行不显示该按钮**;平铺字段行不显示。
- [ ] **Step 2: 实现**:行级小按钮(既有 `.cand-btn` 同位样式),onClick:
  `setByPath(next, 同容器下一可用下标(现数组长度)同字段路径, '')`;可见性 = `isDeepField(f) &&
  !inCarryContainer(f)`(D9:carry 容器上不显示 — compose 时加同级=接管整包,按钮出现即合法)。
- [ ] **Step 3**:vitest + vue-tsc 绿 → Commit `feat(web): 深层字段「+ 同级」— carry 容器豁免`

---

## 终验(两批完成后)

- [ ] `python -m pytest tests/plate -q` 全绿;`npx vitest run` + `npx vue-tsc --noEmit` 全绿
- [ ] 现场目检(5173 HMR):dispatch 步骤表单 — supplier 深层行带角标/上级标注;对深层行做
  「注入响应变量」→ 提示条 + 兜底行;清空 → 容器剪枝;「+ 同级」→ 派生行即现
- [ ] 汇报:按 finishing-a-development-branch 呈选项(该分支尚有用户未提交 WIP,合并/PR 决策留用户)
