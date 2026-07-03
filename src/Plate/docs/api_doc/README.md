# api_doc 模块(Markdown API 文档生成器)

> 路径:`src/Plate/api_doc/`
> 文档版本:对应源码 commit `e0be7bf` 之后
> 文档目标读者:第一次接触 Plate 文档工具链的工程师 / API 文档作者 / 静态站点生成器作者

## 0. 写在最前面(给"完全不了解的人"的话)

如果你从没听过 `Gimbal` / `Plate` / `api_doc`,先读 [../overview.md](../overview.md)。读完你应该能理解:

> **"api_doc 子包是 Plate 子系统的'只读渲染层'(Phase 3 §4.1)。它把 `EndpointSpec` (L1) + `EndpointDoc` (L2) 转成人类可读的 Markdown,供文档站点 / 内部 wiki / AI skill 上下文使用。本模块全程只读、不修改 spec、不触发 IO、不 import service 子包。"**

简单讲,api_doc 的全部职责可以浓缩为一句话:

> **"我有一堆 `EndpointSpec` 和 `EndpointDoc`,我想让它们变成可在 GitHub wiki 渲染的 Markdown。"**

下面是这份文档的目录。

```
1. 模块定位与目录结构
2. render.py        ─ 渲染核心(库形态)
3. cli.py           ─ plate doc CLI 入口
4. __main__.py      ─ python -m Plate.api_doc 等价入口
5. __init__.py      ─ 包级 re-export
6. 输出示例(渲染前 / 渲染后)
7. 设计哲学与决策记录
8. 典型使用示例(库调用 / CLI / 自定义渲染)
9. 不变量总结
10. 设计权衡与未来工作
```

---

## 1. 模块定位与目录结构

`Plate/api_doc/` 是 Plate 子系统的 **Phase 3 文档层**(对应 `design/phase3/PR-3.1.md`)。它的设计目标是把机器可读 spec 翻译成人能直接阅读的 Markdown,服务于以下消费者:

| 消费者                | 怎么用 api_doc                                              |
| --------------------- | ------------------------------------------------------------- |
| 文档站点              | 跑 `plate doc fin` 把输出粘到 GitBook / Notion / MkDocs      |
| 内部 wiki             | CI 拉所有 service,合并成"全公司 API 一览"                    |
| AI skill 上下文       | 训练/检索时把 Markdown 当成 RAG 语料                          |
| 工程师 review         | 写 PR 时对照 Markdown 看"我加的 spec 出现在哪"               |

物理布局(4 个文件):

```
Plate/api_doc/
├── __init__.py    ← 包级 re-export(render_endpoint, render_service)
├── __main__.py    ← python -m Plate.api_doc 入口
├── cli.py         ← plate doc CLI 实现(库形态优先,CLI 是薄包装)
└── render.py      ← Markdown 渲染核心(纯函数,无副作用)
```

> **为什么 render 和 cli 拆两个文件?** render 是"纯函数 + 零副作用"的库,cli 是"接 argv / 调 registry / 写 stdout"的壳。两者关注点完全不同,合并会让测试困难(纯函数 + 副作用代码混在一起)。

---

## 2. `render.py` ── 渲染核心(库形态)

**职责**:把 `EndpointSpec` 列表 + L2 doc 查询函数 → 一段 Markdown。这是整个 api_doc 子包的"引擎"。

### 2.1 物理结构(159 行,2 个公开函数 + 3 个内部符号)

| 符号                | 类型     | 作用                                |
| ------------------- | -------- | ----------------------------------- |
| `render_endpoint`   | 函数     | 渲染单个 endpoint                   |
| `render_service`    | 函数     | 渲染整个 service                    |
| `_CATEGORY_ORDER`   | tuple    | 分类排序(固定顺序)                 |
| `_CATEGORY_LABELS`  | dict     | 分类中文标签                        |
| `_format_path`      | 内部     | 元组路径 → 字符串                   |

### 2.2 三个核心不变量(模块 docstring 钉死)

> **B2 原则(渲染层零副作用)**:本模块**只读** spec 与 doc,**不**做任何修改,**不**触发任何 IO,**不** import 任何 service 子包。

为什么这么严:

- **可测性**:渲染函数纯,可以在 0 mock 0 fixture 下单元测试
- **可嵌入**:任何 Python 进程(测试 / CI / 文档站点 / IDE 插件)都能调,不会"意外触发网络请求"或"改 registry 状态"
- **可重入**:多次渲染同一份 spec,得到字节级相同输出(见字节级约定)

### 2.3 `_CATEGORY_ORDER` 与 `_CATEGORY_LABELS`

```python
_CATEGORY_ORDER: tuple[EndpointCategory, ...] = (
    EndpointCategory.BUSINESS,
    EndpointCategory.QUERY,
    EndpointCategory.TOOL,
)

_CATEGORY_LABELS: dict[EndpointCategory, str] = {
    EndpointCategory.BUSINESS: "业务接口",
    EndpointCategory.QUERY: "查询接口",
    EndpointCategory.TOOL: "工具接口",
}
```

| 决策                                | 为什么                                                          |
| ----------------------------------- | --------------------------------------------------------------- |
| 固定 tuple 而非枚举的 `__iter__`    | 显式声明顺序是"业务 → 查询 → 工具",未来加新 category 时强制 review 这里的顺序 |
| 业务优先于查询                      | 业务流程地图(reader 关心"我能改什么"先于"我能查什么")            |
| 工具兜底                            | 未来加 TOOL 类端点时,它出现在最后,语义最弱                      |
| 中文 label 而非英文 enum value       | 输出面向中文读者;enum value 仍在括号内同时出现,机器可读        |

### 2.4 `_format_path` 内部函数

```python
def _format_path(path: tuple[str, ...] | list[str]) -> str:
    """``(a, b, c)`` → ``"a.b.c"``,空元组 → ``"<body>"``。"""
    if not path:
        return "<body>"
    return ".".join(path)
```

**为什么用 `.` 而不是 `/`?** 因为这是 `FieldBinding` 的逻辑路径(在 Pydantic 模型字段名之间导航),不是 wire path。`from_path=("data", "audit_id")` 表示"在 data 字典里找 audit_id 键"。

**`<body>` 标记**:空元组表示"binding 来自整个 request body",不指定具体字段。`FieldBinding.from_path=()`(理论可能)渲染成 `<body>` 表达"从 body 整体取"。

### 2.5 `render_endpoint(spec, doc=None)` 详解

```python
def render_endpoint(
    spec: EndpointSpec,
    doc: EndpointDoc | None = None,
) -> str:
    parts: list[str] = [f"### {spec.method} {spec.path}"]
    ...
```

**渲染结构**(注释版):

```markdown
### {METHOD} {PATH}                        ← 1. 标题(method + path)
- **summary**: {spec.summary}              ← 2. 业务一句话(如果有)
- **category**: {value} (中文 label)        ← 3. 分类(枚举值 + 中文)
- **mutates_state**: {True/False}          ← 4. CT 探测用
- **tags**: {tag1, tag2, ...}              ← 5. 业务标签(如果有)
- **request**: `{ClassName}`               ← 6. 请求数据类名
- **responses**:                            ← 7. 响应表
  - `{status_code}`: `{ClassName}`
  - ...
- **字段绑定(bindings)**:                 ← 8. binding 列表(如果有)
  - `{to_path}` ← `{from_path}` [transform: X] [optional]
- **业务备注**: (无 L2 注释)              ← 9a. L2 缺失
  或
- **注意事项(notes)**:                    ← 9b. L2 存在
  - {note1}
  - {note2}
- **前置条件(requires)**:
  - {req1}
- **see_also**: {path1, path2, ...}
- **L2 summary**: {doc.summary if != spec.summary}    ← 9c. L2 summary 补充(只有与 L1 不同时才显示)
```

**9 个段位都做了"如果为空则省略"** — 渲染输出随 spec 的实际丰富度变化,避免空字段污染。

**关键决策**:
- L1 `summary` 与 L2 `summary` 都填了,且**文本一致** → 只显示 L1,避免冗余
- L2 `summary` 填了但与 L1 不同 → 显示 `L2 summary:`,作为"对 L1 的补充"
- L2 完全没填 → 显示 `(无 L2 注释)`,不抛错

### 2.6 `render_service(service, specs, doc_lookup=None)` 详解

```python
def render_service(
    service: str,
    specs: list[EndpointSpec],
    doc_lookup: Callable[[str], EndpointDoc | None] | None = None,
) -> str:
    by_cat: dict[EndpointCategory, list[EndpointSpec]] = {c: [] for c in _CATEGORY_ORDER}
    for spec in specs:
        by_cat[spec.category].append(spec)

    out: list[str] = [f"# {service} 服务 API 文档\n"]

    total = len(specs)
    with_l2 = 0
    if doc_lookup is not None:
        with_l2 = sum(1 for s in specs if doc_lookup(s.path) is not None)
    out.append(f"> 共 {total} 个端点,{with_l2} 个有 L2 注释\n")
    ...
```

**算法步骤**:

1. 按 category 分桶(`by_cat`)
2. 写表头(`# {service} 服务 API 文档`)
3. 统计:总端点数 + 有 L2 doc 的端点数 → 写引用块
4. 按 `_CATEGORY_ORDER` 顺序遍历 category 桶:
   - 桶空 → 跳过整个 category 段
   - 桶非空 → 写小标题(`## 业务接口(BUSINESS, 14)`),桶内按 path 字典序排
5. 对每个 spec 调 `render_endpoint(spec, doc=doc_lookup(spec.path))`
6. 用空行分隔不同 category 块

**`doc_lookup` 是函数注入**:

```python
Callable[[str], EndpointDoc | None] | None
```

- 传 `None` → 该 service 完全没有 L2,所有 endpoint 都显示 "(无 L2 注释)"
- 传函数 → 调 `doc_lookup(path)` 拿 doc(可能返回 `None` 表示该端点没 L2)
- 这是 **"依赖注入"** 模式:render 不直接 import 任何 `dannotations` 模块,由 caller(CLI 或其他)负责注入

**为什么按 path 字典序而不是按"业务流顺序"?**

- 字典序 **稳定 + 字节级可重现** + 不需要"业务流定义"
- 业务流顺序需要额外维护一份"端点依赖图",ROI 低(读者能自己在 31 个 spec 里找到主链)

### 2.7 bindings 渲染的"transform / optional"细节

```python
if spec.bindings:
    parts.append("- **字段绑定(bindings)**:")
    for fb in spec.bindings:
        from_path = _format_path(fb.from_path)
        to_path = _format_path(fb.to_path)
        extra = ""
        if fb.transform:
            extra += f" [transform: {fb.transform}]"
        if not fb.required:
            extra += " [optional]"
        parts.append(f"  - `{to_path}` ← `{from_path}`{extra}")
```

**两个修饰符**:
- `[transform: xxx]` — 表示"取到源值后还要做变换"(例如 `int(s)`, `s.lower()`)
- `[optional]` — 表示"源值不存在时 binding 不强制要求"(与 `required=True` 相对)

**为什么 `extra` 用字符串拼接而非 list?** 表达"有/无"的多标记组合时,字符串拼接更短,而 list join 还要处理空 list 的边界。

### 2.8 L2 doc 的"折叠渲染"策略

```python
if doc is None:
    parts.append("- **业务备注**: (无 L2 注释)")
else:
    if doc.summary and doc.summary != spec.summary:
        parts.append(f"- **L2 summary**: {doc.summary}")
    if doc.notes:
        parts.append("- **注意事项(notes)**:")
        for n in doc.notes:
            parts.append(f"  - {n}")
    if doc.requires:
        parts.append("- **前置条件(requires)**:")
        for r in doc.requires:
            parts.append(f"  - {r}")
    if doc.see_also:
        parts.append(f"- **see_also**: {', '.join(doc.see_also)}")
```

**L1/L2 同名 summary 的去重**:L1 的 `summary` 已经在前面渲染过,如果 L2 的 `summary` 文本相同,不重复显示。只有 L2 提供了"对 L1 的补充/扩展说明"时才显示 `L2 summary:` 段。

**L2 缺字段的"折叠"**:`notes` 为空 → 整段不显示;`requires` 为空 → 整段不显示;`see_also` 为空 → 整段不显示。这是 **"零噪声"** 原则。

---

## 3. `cli.py` ── plate doc CLI 入口

**职责**:接 `argv` 解析 → 调 `registry.warm` 拉 spec → 调 `render_service` 渲染 → 写 stdout。这是 **"CLI 是薄包装"** 原则的体现(对应 PLATE_EVOLUTION §4.3 论证的 B1 原则)。

### 3.1 物理结构(146 行,1 个公开函数 + 1 个内部工厂表 + 1 个 lazy helper)

| 符号                       | 类型       | 作用                                              |
| -------------------------- | ---------- | ------------------------------------------------- |
| `main`                     | 函数       | CLI 主入口,返回 process exit code                |
| `_DOC_LOOKUP_FACTORIES`    | dict       | service 名 → L2 doc 查询函数的工厂映射           |
| `_lazy_get_doc(service)`   | 函数       | 延迟 import L2 lookup,避免顶层 import 触发服务包 |
| `_USAGE`                   | str        | `--help` 输出                                      |

### 3.2 入口签名

```python
def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。返回 process exit code。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    ...
```

**`argv` 参数支持注入**:
- 传 `None`(默认)→ 读 `sys.argv[1:]`(真实 CLI 入口)
- 传 `list[str]` → 测 试时直接传 `["fin"]` 之类,不需要 mock `sys.argv`

**返回 int 作为 exit code**:
- 0 全部成功
- 1 部分失败 / 部分跳过
- 2 全部失败 / 参数错误

这种"返回 exit code"模式让 `main` 可测试 — 不需要 `subprocess.run` 验 stdout,直接 `assert main(["fin"]) == 0` 即可。

### 3.3 I/O 编码(Windows 兼容)

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
```

**为什么需要?** Windows 默认 console 是 cp936(GBK),Python 默认 sys.stdout 编码是 cp936。中文 Markdown 在 cp936 下输出会**乱码或抛 UnicodeEncodeError**。`reconfigure(encoding="utf-8")` 强制 stdout/stderr 用 UTF-8。

**`hasattr` 检查**:`sys.stdout.reconfigure` 是 Python 3.7+ 才有,旧 Python 跳过(Linux/macOS 默认就是 UTF-8,Windows 旧版会乱码但不抛错)。

### 3.4 `_DOC_LOOKUP_FACTORIES` 工厂表

```python
_DOC_LOOKUP_FACTORIES: dict[str, Callable[[], Callable[[str], EndpointDoc | None]]] = {
    "fin": lambda: _lazy_get_doc("fin"),
}


def _lazy_get_doc(service: str) -> Callable[[str], EndpointDoc | None]:
    """延迟 import L2 lookup,避免顶层 import 触发 service 子包加载(不变量 #1)。"""
    module = importlib.import_module(f"Plate.{service}.dannotations")
    return module.get_doc
```

**为什么是"工厂"(返回函数)而不是直接传函数?**

```python
# 不行 ❌ — 顶层 import 触发 service 子包
_DOC_LOOKUP_FACTORIES = {
    "fin": importlib.import_module("Plate.fin.dannotations").get_doc,
}
# 此时即使 main(["foo"]) 也会加载 fin.dannotations,违反不变量 #1

# 可以 ✅ — 工厂形式,只在用到 fin 时才 import
_DOC_LOOKUP_FACTORIES = {
    "fin": lambda: _lazy_get_doc("fin"),
}
```

**不变量 #1**(见 [../overview.md](../overview.md) 的核心原则表):`api_doc` 不 import 任何 service 子包。`lambda` 闭包让"按需 import"成为可能 — 跑 `plate doc home` 时,fin 子包不会被动加载。

**新 service 接入方式**(在 cli.py 注释里写明):

```python
# 1. 在 Plate.<svc>.dannotations 实现 get_doc(path)
# 2. 在本字典加一行 "<svc>": lambda: _lazy_get_doc("<svc>")
# 渲染层无任何改动
```

这是 **"扩展点"** 模式 — 渲染层是封闭的(open-closed),新增 service 不需要碰 render.py。

### 3.5 `main(argv)` 主循环详解

```python
success_services: list[str] = []
skipped_services: list[str] = []
failed_services: list[str] = []
rendered_blocks: list[str] = []

for svc in services:
    try:
        specs = registry.warm([svc])
    except Exception as e:
        print(f"[plate doc] service '{svc}' 收集失败: {e}", file=sys.stderr)
        failed_services.append(svc)
        continue

    if not specs:
        print(f"[plate doc] service '{svc}' 已 collect 但无 spec,跳过", file=sys.stderr)
        skipped_services.append(svc)
        continue

    factory = _DOC_LOOKUP_FACTORIES.get(svc)
    doc_lookup = factory() if factory else None
    try:
        rendered = render_service(svc, specs, doc_lookup)
    except Exception as e:
        print(f"[plate doc] service '{svc}' 渲染失败: {e}", file=sys.stderr)
        failed_services.append(svc)
        continue

    rendered_blocks.append(rendered)
    success_services.append(svc)

if rendered_blocks:
    sys.stdout.write("\n---\n\n".join(rendered_blocks))
```

**5 个分类桶**:用 3 个 list 区分 3 种结果状态(success / skipped / failed),便于最后决定 exit code。

**为什么每个 service 用单独的 `try/except`?**
**部分失败不阻断全部** — 跑 `plate doc fin foo bar` 时,即使 foo 和 bar 都失败,fin 仍然成功渲染。这是 **"健壮优先"** 而非 "全或无"。

**`registry.warm([svc])` 是什么?**
在 [../core/README.md](../core/README.md) 里 `warm` 是 registry 的"强制加载 + 返回 spec 列表"方法。这里用它,因为:

- 它**保证 spec 已加载**(不会有"registry 还没拉 fin 就被外部 reset 了"的边角案例)
- 它**直接返回 list[EndpointSpec]**(不用再走 `registry._index` filter)

**`\n---\n\n` 分隔符**:
- `\n---\n\n` 是 Markdown 的"水平分割线 + 段落间距"
- 让多个 service 的输出在视觉上清晰分开

### 3.6 退出码策略

```python
# 退出码策略:与 POSIX 工具一致——全部成功 0,部分失败 1,全部失败 2。
if failed_services and not success_services:
    return 2
if failed_services or skipped_services:
    return 1
return 0
```

| 条件                                      | exit code | 含义                          |
| ----------------------------------------- | --------- | ----------------------------- |
| 全部 success                              | 0         | 全部渲染 OK                   |
| 至少 1 success + 至少 1 failed/skipped    | 1         | 部分渲染 OK(警告级失败)       |
| 全部 failed / 无 success                  | 2         | 致命错误(参数错 / 全失败)     |

**与 POSIX 工具一致**:grep 返回 1 表示"没找到",返回 2 表示"出错"。Plate 沿用这套语义,让 shell 脚本能直接处理。

### 3.7 错误消息格式

```
[plate doc] service 'foo' 收集失败: No module named 'Plate.foo'
[plate doc] service 'bar' 已 collect 但无 spec,跳过
[plate doc] service 'baz' 渲染失败: ...
```

**`[plate doc]` 前缀**:让 stderr 消息**一眼能识别来源** — 在多工具 pipeline 里,这条规则救命(其他工具的错误可能也打到 stderr)。

**为什么用 stderr 而非 stdout?** stdout 是"数据流"(渲染出的 Markdown),stderr 是"诊断流"(警告 / 错误)。两者分离,便于 `plate doc fin > out.md`(只重定向数据流,诊断信息仍可看到)。

---

## 4. `__main__.py` ── python -m Plate.api_doc 等价入口

**职责**:让 `python -m Plate.api_doc <args>` 等价于 `plate doc <args>`(假设装包后会有 `plate` 命令)。

### 4.1 物理结构(7 行,1 行 import + 1 行 raise)

```python
"""``python -m Plate.api_doc`` 入口。等价于 ``plate doc`` CLI,但不需要装包。"""
from __future__ import annotations

from Plate.api_doc.cli import main

raise SystemExit(main())
```

**为什么是 `raise SystemExit(main())` 而不是 `if __name__ == "__main__"` 块?**

- 这个文件**只**作为 `-m` 入口用,不会有其他 import 它的场景
- `if __name__ == "__main__"` 块写法是"双形态"(既可 import 又可执行),这里不需要
- `raise SystemExit` 让 `main()` 的返回值(0/1/2)直接成为 Python 进程的 exit code,**少一层包装**

### 4.2 与 `cli.py` 的关系

`cli.py` 的 `if __name__ == "__main__"` 块也直接调 `main()`(在 cli.py L145–146):

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

**这两个文件的关系**:
- `cli.py`:`python cli.py` 也能跑(罕见用法)
- `__main__.py`:`python -m Plate.api_doc` 跑(标准用法)

两者底层都调同一个 `main()`,**单一逻辑源**,避免双份实现漂移。

---

## 5. `__init__.py` ── 包级 re-export

**职责**:把 `render.py` 的两个公开函数 re-export,让用户能 `from Plate.api_doc import render_endpoint, render_service`(库调用场景)。

```python
from .render import render_endpoint, render_service

__all__ = ["render_endpoint", "render_service"]
```

**为什么不 re-export `main`?**
- `main` 是 CLI 入口,**不**应该被库用户直接 import
- 想跑 CLI 就 `python -m Plate.api_doc`,显式胜过隐式
- `__all__` 只列"库形态"的公开符号,`main` 不在里面

**为什么不 re-export `_DOC_LOOKUP_FACTORIES`?**
- 它是 CLI 内部状态
- 库用户如果想"加新 service 渲染",应该自己实现 `doc_lookup` 函数并注入到 `render_service`,**不需要**改 CLI 内部表
- 让 `__all__` 保持精简,避免 API 表面膨胀

---

## 6. 输出示例(渲染前 / 渲染后)

### 6.1 渲染前(L1 + L2 原始数据)

```python
# 一个 spec 的 L1:
orderDetail = EndpointSpec(
    method="POST",
    path="/api/order/order/orderDetail",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=OrderDetailRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderDetailData},
    summary="订单详情查询",
    tags=["order", "detail", "query"],
)

# 同一端点的 L2(如果人工写了):
_ENDPOINT_DOCS["/api/order/order/orderDetail"] = EndpointDoc(
    summary="按订单 ID 查询订单详情,返回订单全字段快照",
    notes=("限流:每用户 10 QPS", "时区:所有时间字段为 UTC+8"),
    requires=("已登录", "订单属于当前用户"),
    see_also=("/api/order/order/orderAdd",),
)
```

### 6.2 渲染后(Markdown)

```markdown
# fin 服务 API 文档

> 共 31 个端点,1 个有 L2 注释

## 业务接口(BUSINESS, 14)

### POST /api/order/orderEntrust/orderAdd
- **summary**: 委托订单新增
- **category**: BUSINESS (业务接口)
- **mutates_state**: True
- **tags**: order, entrust, write
- **request**: `OrderEntrustOrderAddRequest`
- **responses**:
  - `200`: `CommonResponseEnvelope`
- **业务备注**: (无 L2 注释)

... (其他 BUSINESS 端点)

## 查询接口(QUERY, 17)

### POST /api/order/order/orderDetail
- **summary**: 订单详情查询
- **category**: QUERY (查询接口)
- **mutates_state**: False
- **tags**: order, detail, query
- **request**: `OrderDetailRequest`
- **responses**:
  - `200`: `CommonResponseEnvelope`
- **L2 summary**: 按订单 ID 查询订单详情,返回订单全字段快照
- **注意事项(notes)**:
  - 限流:每用户 10 QPS
  - 时区:所有时间字段为 UTC+8
- **前置条件(requires)**:
  - 已登录
  - 订单属于当前用户
- **see_also**: /api/order/order/orderAdd

### POST /api/home/audit/auditDetail
- **summary**: 审核详情查询
- **category**: QUERY (查询接口)
- **mutates_state**: False
- **tags**: audit, detail, query
- **request**: `AuditDetailRequest`
- **responses**:
  - `200`: `CommonResponseEnvelope`
- **字段绑定(bindings)**:
  - `audit_id` ← `data.audit_id`
- **业务备注**: (无 L2 注释)

... (其他 QUERY 端点)
```

### 6.3 关键渲染点解释

| 段位                     | 含义                                                                 |
| ------------------------ | -------------------------------------------------------------------- |
| `# fin 服务 API 文档`    | 一级标题,doc 站点用 `fin` 作为目录                                  |
| `> 共 31 个端点,1 个有 L2 注释` | 引用块,一眼看出 L2 覆盖进度                                  |
| `## 业务接口(BUSINESS, 14)` | 二级标题 + 分类枚举值 + 计数,机器 + 人都能扫                   |
| `### POST /api/...`      | 三级标题,method + path 是端点的"全局唯一标识"                       |
| `- **request**: \`OrderDetailRequest\`` | 显式反引号包类名,渲染时是等宽字体 + 不会被 Markdown 解析  |
| `**字段绑定(bindings)**` | 用粗体作为段位标题,不用下划线(避免与 Markdown 链接语法冲突)         |
| `(无 L2 注释)`           | 显式标记"此处应有但缺失",未来 PR 补 L2 时这个标记自动消失          |

---

## 7. 设计哲学与决策记录

### 7.1 库形态优先,CLI 是薄包装(PLATE_EVOLUTION §4.3 B1)

`render.py` 是核心,`cli.py` 是 `argv` 解析 + 调 `render_service` + 写 stdout 的壳。

- **库形态** 让 `render_endpoint` / `render_service` 可独立 import,IDE 插件 / 文档站点 / 测试都能复用
- **CLI 形态** 解决"日常用命令行"的场景,但**只是库的薄包装**(cli.py 的 50 行核心逻辑里,只有 `main` 函数有副作用)

### 7.2 渲染层零副作用(模块 docstring B2)

详见 §2.2。

`render_*` 三个不变量:
1. **只读**:不修改传入的 spec / doc
2. **无 IO**:不读文件、不写文件、不发网络请求
3. **不 import service 子包**:render.py 顶部只有 `from Plate.doc import EndpointDoc` 和 `from Plate.spec import EndpointCategory, EndpointSpec`,**绝不** import 任何 `Plate.fin` / `Plate.home` 等具体服务

这让渲染函数可以 **"无配置、无环境依赖"** 地运行 — 你能在 CI、notebook、IDE 插件里随便调,不会意外触发服务包加载。

### 7.3 业务分类固定顺序(BUSINESS → QUERY → TOOL)

详见 §2.3。

为什么不按字母序?
- 业务流程地图(reader 关心"我能改什么"先于"我能查什么")
- 按"业务强度"降序,让"重的操作"显眼

为什么不按 spec 出现顺序?
- spec 出现顺序由 endpoints.py 文件结构决定,经常调整
- category 顺序是**业务语义**,变更需要 code review

### 7.4 字节级稳定(对齐 manifest)

`render_endpoint` 和 `render_service` 输出是 **纯函数结果**:

- 输入相同(spec 列表 + doc_lookup 行为)→ 输出字节级相同
- L1 spec 的 `to_dict()` 字节级稳定(详见 [../spec/README.md](../spec/README.md))
- L2 doc lookup 是 dict 查表,顺序确定
- `sorted(..., key=lambda s: s.path)` 让 endpoint 顺序确定

这意味着 **CI 可以拿 `plate doc fin > expected.md`,做 `diff actual.md expected.md`** 来保证"业务主链没被改坏"。

### 7.5 不 import service 子包(不变量 #1)

`api_doc` 包不 import 任何 `Plate.fin` / `Plate.home` 等具体服务包。这与 §2.2 的 B2 一脉相承。

**如何做到?**

- `render.py` 顶部零 service import
- `cli.py` 通过 `_DOC_LOOKUP_FACTORIES` 工厂表**延迟** import — `python -m Plate.api_doc home` 时,`Plate.fin` 不会被加载

**为什么这么严?**

- 文档生成器在 CI 里跑,如果不小心 import 了 fin,会触发 fin 包下 31 个 spec 的 Pydantic 校验(慢 ~100ms × 31 = 3s)
- 跑 `plate doc home` 时,加载 fin 是无意义的副作用
- 单元测试时不希望"import api_doc"就触发 fin 包的副作用

### 7.6 doc_lookup 函数注入(依赖反转)

`render_service` 不直接调 `Plate.fin.dannotations.get_doc`,而是接 `Callable[[str], EndpointDoc | None] | None` 作为参数。

- **测试时**:传 `lambda path: None`(所有端点都"无 L2 注释"),不用 mock `dannotations`
- **新 service 接入**:写自己的 `get_doc`,注入到 `render_service` 参数,**不用改** render.py
- **离线渲染**:不依赖任何 service 的 dannotations 模块,只依赖 spec 列表

### 7.7 部分失败不阻断(健壮优先)

详见 §3.5。`plate doc fin foo` 中 foo 失败不影响 fin 渲染,exit code 1 表示"部分成功"。

### 7.8 stdout/stderr 分离

- **stdout**:渲染出的 Markdown(可被 `>` 重定向)
- **stderr**:诊断信息(警告 / 错误),不会被 `>` 重定向捕获

这是 Unix 工具的惯例,Plate 严格遵守。

### 7.9 exit code 与 POSIX 工具一致

详见 §3.6。0 成功 / 1 部分失败 / 2 致命错误,与 grep / find / make 等工具一致。

---

## 8. 典型使用示例

### 8.1 库调用(最灵活)

```python
from Plate import registry
from Plate.api_doc import render_service
from Plate.fin.dannotations import get_doc as fin_get_doc

# 1. 拉 fin 服务的全部 spec
specs = registry.warm(["fin"])

# 2. 渲染成 Markdown 字符串
md = render_service("fin", specs, doc_lookup=fin_get_doc)

# 3. 写到文件 / 入库 / 上传 wiki
with open("docs/fin-api.md", "w", encoding="utf-8") as f:
    f.write(md)
```

### 8.2 单端点渲染(用于 IDE 提示 / 单页文档)

```python
from Plate.fin.endpoints import orderDetail
from Plate.fin.dannotations import get_doc

path = orderDetail.path  # "/api/order/order/orderDetail"
md = render_endpoint(orderDetail, doc=get_doc(path))
print(md)
```

输出:

```
### POST /api/order/order/orderDetail
- **summary**: 订单详情查询
- **category**: QUERY (查询接口)
- **mutates_state**: False
- **tags**: order, detail, query
- **request**: `OrderDetailRequest`
- **responses**:
  - `200`: `CommonResponseEnvelope`
- **业务备注**: (无 L2 注释)
```

### 8.3 自定义 doc_lookup(测试 / 离线场景)

```python
from Plate.api_doc import render_service
from Plate import registry

# 测试时:所有 L2 都视为"无注释"
def always_none(path):
    return None

specs = registry.warm(["fin"])
md = render_service("fin", specs, doc_lookup=always_none)
assert "无 L2 注释" in md
```

### 8.4 CLI 调用(最常见)

```bash
# 渲染 fin 服务的 Markdown 文档
python -m Plate.api_doc fin > docs/fin-api.md

# 多个 service(中间用 --- 分隔)
python -m Plate.api_doc fin foo bar > docs/all-api.md

# 帮助
python -m Plate.api_doc --help
```

### 8.5 CI 集成(渲染 + 校验)

```python
# ci/validate_docs.py
import subprocess
import hashlib
from pathlib import Path

def main():
    # 1. 跑 CLI 拿当前渲染结果
    out = subprocess.run(
        ["python", "-m", "Plate.api_doc", "fin"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit(f"plate doc 失败: {out.stderr}")

    # 2. 字节级 SHA256
    actual = hashlib.sha256(out.stdout.encode("utf-8")).hexdigest()
    expected_path = Path("ci/expected-fin-api.sha256")
    expected = expected_path.read_text().strip()

    if actual != expected:
        raise SystemExit(
            f"fin 文档渲染结果变化!\n"
            f"  实际: {actual}\n"
            f"  期望: {expected}\n"
            f"如果是有意改动,运行: python -m Plate.api_doc fin | "
            f"python -c \"import sys, hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())\" "
            f"> ci/expected-fin-api.sha256"
        )
    print("OK: fin 文档渲染结果与 CI 基线一致")
```

### 8.6 注入到 MkDocs / GitBook

```yaml
# mkdocs.yml
nav:
  - API 文档:
    - fin: ./generated/fin-api.md
```

```bash
# 生成步骤(在 mkdocs build 之前跑)
python -m Plate.api_doc fin > docs/generated/fin-api.md
mkdocs build
```

### 8.7 exit code 处理(shell 脚本)

```bash
#!/bin/bash
set -e

python -m Plate.api_doc fin > docs/fin-api.md
# exit code 0 → 全部成功
# exit code 1 → 部分失败(警告,继续)
# exit code 2 → 全部失败(中断)

if [ $? -eq 2 ]; then
    echo "FATAL: plate doc 全部失败" >&2
    exit 1
fi
```

---

## 9. 不变量总结

| #   | 不变量                                                                              | 守护位置                              |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------- |
| 1   | api_doc 包不 import 任何 service 子包(B2 原则)                                       | render.py / cli.py 顶部 import 区     |
| 2   | render_* 函数无副作用(只读 + 无 IO)                                                  | render.py 全文(无 print / 无 file IO) |
| 3   | 渲染输出按 `BUSINESS → QUERY → TOOL` 固定顺序                                        | `_CATEGORY_ORDER` 元组                |
| 4   | 同 category 内 endpoint 按 path 字典序                                              | `sorted(..., key=lambda s: s.path)`   |
| 5   | L2 doc 缺失时显示 `(无 L2 注释)`,不抛错                                              | `render_endpoint` 的 `if doc is None` 分支 |
| 6   | L1/L2 同名 summary 不重复显示                                                       | `if doc.summary and doc.summary != spec.summary` |
| 7   | 渲染输出字节级稳定(纯函数)                                                          | render 全部用纯函数 + 排序             |
| 8   | stdout 是数据流,stderr 是诊断流                                                     | `print(..., file=sys.stderr)`         |
| 9   | stdout/stderr 在 Windows 上强制 UTF-8                                               | `sys.stdout.reconfigure(encoding="utf-8")` |
| 10  | `_DOC_LOOKUP_FACTORIES` 用工厂(lambda)延迟 import                                   | `_DOC_LOOKUP_FACTORIES` 字典定义      |
| 11  | `main` 接受 `argv` 注入(可测)                                                       | `def main(argv: list[str] | None = None)` |
| 12  | exit code 与 POSIX 一致(0/1/2)                                                      | `main` 末尾三分支 return              |
| 13  | 渲染失败的 service 计入 `failed_services`,不阻断其他 service                       | `try/except` 包裹每个 service          |
| 14  | `__init__.py` 只 re-export `render_endpoint` / `render_service`,不暴露 `main`     | `__init__.py` 内容                    |
| 15  | `_format_path` 空元组 → `<body>`                                                    | `_format_path` 内部判断                |
| 16  | `binding` 渲染顺序:`to_path ← from_path`,transform 标 `[transform: X]`,非必填标 `[optional]` | `render_endpoint` 的 bindings 段     |

---

## 10. 设计权衡与未来工作

### 10.1 当前权衡

| 决策                                       | 收益                                       | 代价                                       |
| ------------------------------------------ | ------------------------------------------ | ------------------------------------------ |
| 库形态优先,CLI 是薄包装                    | render 可独立测、可嵌入                     | 简单的 CLI 内部需要写"if not 库"分支       |
| 渲染层零副作用(B2)                          | 测试简单、可重入                           | 不能在渲染时做"自动补充"(比如自动查 git blame) |
| 业务分类固定顺序(BUSINESS→QUERY→TOOL)       | reader 视角的"流程地图"                   | 加新 category 需要改 tuple 顺序            |
| 不 import service 子包(不变量 #1)           | CI 跑 `plate doc home` 不触发 fin 包        | cli 必须用工厂表延迟 import,稍复杂          |
| doc_lookup 函数注入                        | 测试容易 + 离线渲染                        | 调用方多写一行 `lambda`                    |
| 部分失败不阻断                              | 健壮                                       | 退出码 1 不是真正的"成功"                  |
| stdout 是 Markdown,stderr 是诊断            | Unix 惯例                                  | Windows 老 console 看 stderr 不友好        |
| 不展开 JSON schema(只显示类名)              | 渲染简洁                                   | reader 看不到具体字段(需要点链接)         |
| 中文 category label                         | 中文读者友好                                | 国际化场景需要再加英文 label               |
| `__main__.py` 顶层 `raise SystemExit`       | 进程 exit code 与 main 返回值一致         | 不可被 import 后调 main()(强制副作用)     |
| 不在 render 里做权限检查                    | 渲染是纯函数                               | 文档里可能含敏感 path(比如内部管理 API)   |

### 10.2 未来工作

1. **JSON schema 展开**:在 `request` / `responses` 段位后,加一个折叠的"```json ... ```"代码块,展示 Pydantic 模型的字段
2. **多语言 label**:`_CATEGORY_LABELS` 加英文版,通过 CLI flag `--lang` 切换
3. **HTML 输出**:加 `render_service_html`,与 Markdown 并列
4. **绑定关系图**:在文档末尾输出一个 Mermaid 图,可视化 `bindings` 跨端点数据流
5. **CI 字节级校验**:类似 §8.5 的脚本,固化"文档渲染结果与基线一致"
6. **跨服务文档合并**:`plate doc fin home user` 输出"全公司 API 一览",按 category 聚合
7. **JSON 端点**:`plate doc --format json fin` 输出 JSON 而不是 Markdown,便于其他工具消费
8. **交互式 HTML**:基于现有 Markdown 渲染,用 React/Vue 包一个"端点导航 + 请求构造器"
9. **新 service 接入工具**:`plate add-service home` 自动生成 `dannotations/__init__.py` 骨架 + `cli.py` 工厂表行

### 10.3 与整体 Plate 哲学的一致性

| 哲学原则(见 [../overview.md](../overview.md)) | api_doc 模块怎么落地                                              |
| -------------------------------------------- | --------------------------------------------------------------- |
| 零侵入(不污染后端代码)                       | api_doc 只读 spec,后端 Gin 代码不需要改                        |
| L1/L2 物理分离                                | render 严格按 L1 (spec) / L2 (doc) 两层数据源渲染,L2 缺失静默显示 |
| 懒加载(拉式收集)                             | `_DOC_LOOKUP_FACTORIES` 用工厂延迟 import service 子包         |
| 线程安全                                       | render 纯函数,无共享状态                                        |
| 字节级可重现                                 | 排序 + 纯函数 = 字节级稳定输出,便于 CI 校验                     |
| 契约保真                                      | 渲染不修改 spec / doc 的任何字段                                |
| 声明式 + 命令式混合                           | doc_lookup 是声明式注入,render_service 是命令式调用             |
| 业务标注(category / mutates_state)            | 渲染时把 `category` 显示为分类标题,把 `mutates_state` 显式列出  |

---

> **完结提示**:本文件覆盖 `Plate/api_doc/` 四文件(commit `e0be7bf` 之后)。当新增渲染格式 / 改 category 顺序 / 加新 service 接入时,本文件的 §2、§3、§9 需要同步更新。建议在 `api_doc/` 变更的 PR 模板里挂一条"更新 docs/api_doc/README.md" 的提醒。
