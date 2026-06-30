# PR-3.1: Plate API doc 服务(L1 + L2 合并渲染,Markdown 输出)

> **状态**:🆕 本会话 2026-06-30 启动 Phase 3 §4.1
>
> **对应设计**:[PLATE_EVOLUTION.md §4.1 API doc 服务](../PLATE_EVOLUTION.md) +
> [PLATE_DESIGN.md §5 链路 C 数据流转](../PLATE_DESIGN.md) +
> [BASELINE.md §5 §6 当前状态](../phase2/BASELINE.md)
>
> **业务定位**:Phase 3 三件任务中**成本最低**——`PATH_MODELS` / `EndpointDoc` /
> `EndpointSpec` 现成结构**直接渲染**,无需新协议、无需异步、无需鉴权。

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 完成服务化后,Plate 的 L1 契约层(`EndpointSpec`)+ L2 注释层
(`EndpointDoc`)+ `field_bindings` 都已经结构化,但**没有"人读的视图"**。

- 测试工程师:想知道"fin 服务有哪些端点、每个端点做什么、字段间有何依赖"
- AI skill 编排者:需要 Markdown 形态喂上下文(LLM 偏好)
- oncall 同事:在 PR review 时,需要一份"接口目录"而不是读 Python 源码

**现状**:只能 `from Plate.fin import endpoints` 然后用 IDE 浏览——人类不可直接读。

**Phase 3 §4.1 目标**:给一个 `plate doc` CLI 子命令(或 `Plate.doc.render` 库函数),
输出**合并 L1 + L2** 的 Markdown API 文档:

```
# fin 服务 API 文档

## 业务接口(BUSINESS, 14)
### POST /api/order/order/addOrder
- **summary**: 创建订单
- **tags**: order, write
- **mutates_state**: true
- **依赖**:
  - request.user_id ← POST /api/user/login.data.user_id
- **业务备注**: (无 L2 注释)

## 查询接口(QUERY, 17)
...
```

### 1.2 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 输出格式 | Markdown | LLM 友好;git diff 友好;`markdown`/`rich` 库都不需要 |
| 入口形态 | 库函数 `Plate.doc.render(spec, doc=None) -> str` + CLI `plate doc fin` | Phase 3 §4.3 MCP 之前,库形态优先(对齐 PLATE_EVOLUTION §4.3 论证) |
| L1/L2 合并策略 | 按 `(service, method, path)` 外键 join;L2 缺失时静默降级显示"(无 L2 注释)" | 不强绑 L2 完备性;Phase 1 设计明确"L1/L2 解耦,L2 不阻塞 L1" |
| 排序 | 按 `category`(BUSINESS → QUERY → TOOL)+ path 字典序 | 给读者业务流程地图,而非字母序平铺(对齐 PLATE_DESIGN §0 核心原则) |
| 依赖图渲染 | 行内 `field_bindings` 列表,不出 mermaid 图表 | Mermaid 渲染成本高;读者扫读就够;Phase 4 CT 保活时再考虑图形化 |
| 渲染时机 | **冷数据**——每次 CLI 调用重新渲染;**不缓存** Markdown 产物 | API doc 不大(31 端点 < 50 KB),渲染 < 100ms,缓存复杂度不值 |
| L2 缺失时的可见性 | `(无 L2 注释)` 字样 + 一条汇总 "N/M 端点有 L2 注释" | 提示 L2 维护进度,不阻塞 L1 渲染 |
| service 列表来源 | `from Plate import registry; registry.loaded_services()` + 用户显式参数 | 默认按用户传的 service 名 list,无 magic |

### 1.3 不做什么(明确范围外)

- **不**实现 HTTP 端口(无 `plate doc --serve`)——CLI 直接 stdout 即可,MCP 留 §4.3
- **不**渲染 Pydantic 模型的完整 JSON schema——只显示 `request`/`responses` 模型**类名**
- **不**做 HTML/PDF 输出——Markdown 单一形态,需要时再用 `pandoc` 转
- **不**给 `field_bindings` 反查"这个字段被哪些下游 endpoint 消费"——反向查询留 Phase 4
- **不**实现增量更新监听——每次 CLI 重新渲染,源数据变化靠 git diff 体现

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 | 性质 |
|---|---|---|
| `src/Plate/doc/__init__.py` | 新建:`Plate.doc` 子包(命名区分 `Plate.doc.EndpointDoc` 数据类) | 新建 |
| `src/Plate/doc/render.py` | 新建:`render_endpoint(spec, doc=None) -> str` + `render_service(service, specs, doc_lookup) -> str` | 新建 |
| `src/Plate/doc/cli.py` | 新建:`plate doc <service>...` 入口,接收 args,调 `registry.warm()` 后渲染输出 | 新建 |
| `src/Plate/doc/__main__.py` | 新建:`python -m Plate.doc fin` 入口 | 新建 |
| `src/Plate/__main__.py` | 新建:`python -m Plate` 转发到 `Plate.doc.cli.main` | 新建 |
| `tests/plate/test_doc_render.py` | 新建:渲染层测试(L1 only / L1+L2 / 多 service / 空 service / 排序) | 新建 |
| `tests/plate/test_doc_cli.py` | 新建:CLI 入口测试(集成 `registry.warm` → 渲染) | 新建 |
| `pyproject.toml` | 加 `[project.scripts] plate = "Plate.doc.cli:main"` | 配 1 行 |

**不**修改:`spec.py` / `doc.py` / `core.py` / `manifest.py` / `fin/`(任何子服务)/
`facade/` / `server/`。API doc 是**纯消费层**。

### 2.2 命名冲突解决:`Plate.doc` 子包 vs `Plate.doc.EndpointDoc`

`Plate/doc.py` 是 **Phase 1 已有的 L2 数据类模块**(`EndpointDoc`)。

选项 A:`Plate/doc_render/` 子包(避开 `doc`)
选项 B:把 `doc.py` 改成 `doc/__init__.py`,内部 `EndpointDoc` 仍是 `from . import EndpointDoc`
选项 C:`Plate/api_doc/` 子包(避开 `doc` 命名,语义更准)

**采用 C**——`Plate/api_doc/` 子包。原因:

1. `doc.py` 已稳定(冻结 dataclass,Phase 1 review 通过),改成包是大改动,违反 A6 向后兼容
2. "doc" 在 Plate 上下文已特指 L2 注释,`api_doc` 不会被误读成 L2
3. 与 Phase 3 §4.2 "Mock server" 命名对齐(`Plate/mock_server/`),`api_doc` / `mock_server` /
   `mcp_server` 是同一类命名族

**实际改动文件**(修正 §2.1):

| 文件 | 改动 |
|---|---|
| `src/Plate/api_doc/__init__.py` | 新建子包,导出 `render_service` / `render_endpoint` |
| `src/Plate/api_doc/render.py` | 渲染函数 |
| `src/Plate/api_doc/cli.py` | CLI 入口 |

### 2.3 `render.py` 渲染层 API

```python
# src/Plate/api_doc/render.py

from typing import Callable
from Plate.spec import EndpointSpec, EndpointCategory
from Plate.doc import EndpointDoc  # L2 数据类,Phase 1 已有


_CATEGORY_ORDER = [
    EndpointCategory.BUSINESS,
    EndpointCategory.QUERY,
    EndpointCategory.TOOL,
]
_CATEGORY_LABELS = {
    EndpointCategory.BUSINESS: "业务接口",
    EndpointCategory.QUERY: "查询接口",
    EndpointCategory.TOOL: "工具接口",
}


def render_endpoint(spec: EndpointSpec, doc: EndpointDoc | None = None) -> str:
    """渲染单个 endpoint 的 Markdown。

    L2 doc=None 时,业务备注段显示 "(无 L2 注释)"。
    """
    parts = [f"### {spec.method} {spec.path}"]
    if spec.summary:
        parts.append(f"- **summary**: {spec.summary}")
    parts.append(f"- **category**: {spec.category.value} ({_CATEGORY_LABELS[spec.category]})")
    parts.append(f"- **mutates_state**: {spec.mutates_state}")
    if spec.tags:
        parts.append(f"- **tags**: {', '.join(spec.tags)}")
    if spec.bindings:
        parts.append("- **字段绑定(bindings)**:")
        for fb in spec.bindings:
            from_path = ".".join(fb.from_path) if fb.from_path else "<body>"
            to_path = ".".join(fb.to_path) if fb.to_path else "<body>"
            parts.append(
                f"  - `{to_path}` ← `{from_path}`"
                f"{f' [transform: {fb.transform}]' if fb.transform else ''}"
                f"{'' if fb.required else ' [optional]'}"
            )
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
    return "\n".join(parts) + "\n"


def render_service(
    service: str,
    specs: list[EndpointSpec],
    doc_lookup: Callable[[str], EndpointDoc | None] | None = None,
) -> str:
    """渲染整个 service 的 Markdown。按 category 分组 + path 字典序。

    doc_lookup(path) -> EndpointDoc | None;None 表示所有 endpoint 都没有 L2,
    全部显示 "(无 L2 注释)"。这是 Phase 1 设计允许的状态(详见 PLATE_DESIGN §4)。
    """
    by_cat: dict[EndpointCategory, list[EndpointSpec]] = {c: [] for c in _CATEGORY_ORDER}
    for spec in specs:
        by_cat[spec.category].append(spec)

    out: list[str] = [f"# {service} 服务 API 文档\n"]
    total = len(specs)
    with_l2 = 0
    if doc_lookup is not None:
        with_l2 = sum(1 for s in specs if doc_lookup(s.path) is not None)
    out.append(f"> 共 {total} 个端点,{with_l2} 个有 L2 注释\n")

    for cat in _CATEGORY_ORDER:
        group = sorted(by_cat[cat], key=lambda s: s.path)
        if not group:
            continue
        out.append(f"## {_CATEGORY_LABELS[cat]}({cat.value}, {len(group)})\n")
        for spec in group:
            doc = doc_lookup(spec.path) if doc_lookup else None
            out.append(render_endpoint(spec, doc))
        out.append("")  # 空行分隔
    return "\n".join(out)
```

### 2.4 `cli.py` CLI 入口

```python
# src/Plate/api_doc/cli.py

import sys
from Plate import registry
from Plate.spec import EndpointSpec
from Plate.api_doc.render import render_service

# service 名 → L2 doc 查询函数 的映射。Phase 3 §4.1 只支持 fin。
# 多 service 时,dict 扩展即可。
_DOC_LOOKUP_FACTORIES: dict[str, Callable[[], Callable[[str], "EndpointDoc | None"]]] = {
    "fin": lambda: __import__("Plate.fin.dannotations", fromlist=["get_doc"]).get_doc,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__ or "Usage: plate doc <service> [<service> ...]")
        return 0

    services = argv
    try:
        specs = registry.warm(services)  # 一次 warm,收集所有 service
    except Exception as e:
        print(f"[Plate doc] 收集失败: {e}", file=sys.stderr)
        return 2

    rc = 0
    for svc in services:
        svc_specs = [s for s in specs if _service_of(s) == svc]  # need helper
        if not svc_specs:
            print(f"[Plate doc] service '{svc}' 无 spec,跳过", file=sys.stderr)
            rc = 1
            continue
        factory = _DOC_LOOKUP_FACTORIES.get(svc)
        doc_lookup = factory() if factory else None
        print(render_service(svc, svc_specs, doc_lookup))
    return rc
```

### 2.5 `pyproject.toml` script 入口

```toml
[project.scripts]
plate = "Plate.api_doc.cli:main"
```

调用方式:

```bash
# 安装后
plate doc fin

# 不用装也能跑
python -m Plate.api_doc fin
```

### 2.6 L2 lookup 的服务扩展性

`fin` 之外的 service 没建 `dannotations/` 子包。CLI 用 `_DOC_LOOKUP_FACTORIES` 字典
显式登记,**未登记的 service 也能渲染**(doc_lookup=None,全部显示 "(无 L2 注释)")。

扩展方式:新 service 加一行字典项即可,渲染层无任何改动。

---

### 2.7 本 PR 设计阶段发现的字段偏差(本会话 2026-06-30)

> 后续实装 PR-3.1 的工程师,**先读此节再读 §2.3**,否则会按错误字段名返工。

| PLATE_DESIGN.md §2.1 / §2.2 假设 | 实际 `EndpointSpec` / `FieldBinding` 字段 | 处理 |
|---|---|---|
| `EndpointSpec.field_bindings: tuple["FieldBinding", ...]` | `EndpointSpec.bindings: tuple[FieldBinding, ...]`(PR-D2 简化,去掉 `field_` 前缀) | 用 `bindings` |
| `FieldBinding.field_path` / `source_service` / `source_method` / `source_path` / `source_field_path` / `note` | 实际 `FieldBinding` 只有 `from_path` / `to_path` / `required` / `transform`;**不记录 source endpoint 信息** | 渲染层只显示 from_path → to_path,source 信息靠 cross-binding 反查(Phase 3 §4.2/§4.3 范围) |
| `EndpointDoc` 有 `service / method / path / field_notes / flow_notes / maintainer / updated_at` | 实际 `EndpointDoc` 只有 `summary / notes / requires / see_also`(PR-D3 简化) | 用现 4 字段渲染 |
| `EndpointDoc` 用 `path` 作 key | `Plate.fin.dannotations` 用 `path` 作 key,`get_doc(path) -> EndpointDoc \| None` | `doc_lookup` 接 `Callable[[str], EndpointDoc \| None]` |

**根因**:`PLATE_DESIGN.md §2.1/§2.2/§2.3` 是设计理想态,Phase 1 实施时多次简化(PR-D2 / PR-D3)。
后续 PR-3.1 实装以**当前代码实际字段为准**,PLATE_DESIGN.md 偏差留 Phase 4 单独同步 PR 处理。

---

## 3. 测试用例设计

### 3.1 必测业务场景(`test_doc_render.py`)

| # | 场景 | 断言 |
|---|---|---|
| 1 | 单个 BUSINESS endpoint 渲染 | 含 `### POST /path` + `**category**: business` + summary |
| 2 | 单个 QUERY endpoint | category 字段值 = `query`,mutates_state 提示 |
| 3 | 单个 TOOL endpoint(预留) | 段标题"工具接口"出现 |
| 4 | L2 doc 缺失 | 显示 `(无 L2 注释)`,不抛错 |
| 5 | L2 doc 提供 summary 与 spec.summary 不同 | 输出两行,不冲突 |
| 6 | L2 doc 提供 notes / requires / see_also | 各 section 都出现 |
| 7 | field_bindings 多条 | 每条独占一行,source_* 字段全 |
| 8 | 多 endpoint 同 category | 按 path 字典序 |
| 9 | 多 category 混合 | 输出顺序 BUSINESS → QUERY → TOOL |
| 10 | 空 spec 列表 | 标题 + "> 共 0 个端点" + 不抛错 |
| 11 | tags 为空列表 | "tags" 行不输出(不留空段) |
| 12 | tags 多元素 | 逗号分隔 |

### 3.2 必测 CLI 场景(`test_doc_cli.py`)

| # | 场景 | 断言 |
|---|---|---|
| 1 | `plate doc fin` 跑通,exit 0,stdout 含 `### POST /api/order/order/addOrder` |
| 2 | 多个 service `plate doc fin foo`(foo 未登记) | foo 那段 stderr 警告,exit 1,fin 仍正常输出 |
| 3 | 空 args | 打印 usage,exit 0 |
| 4 | `--help` | 同上 |
| 5 | unknown service | stderr 报错,exit 2 |
| 6 | 渲染输出包含 `> 共 31 个端点` (L2 为空时 with_l2 = 0) | 数字正确 |
| 7 | 渲染后 warm() 的副作用不污染下次调用 | 第二个 service 单独渲染无残留 |

### 3.3 不变量(继承 Phase 2)

- **#1 零侵入**:`from Plate.api_doc import render_service` 不触发 `Plate.fin` 自动加载
  - 验证:在测试里 `import Plate.api_doc` 后检查 `Plate.fin` 不在 `sys.modules`
- **#2 按需加载**:`plate doc fin` 只 warm "fin",不 warm 其他 service
- **#3 契约保真**:不修改 spec/doc 任何字段,只读
- **#4 互补而非替代**:API doc 是**消费层**,不动 L1/L2 任何数据

### 3.4 业务核心测试矩阵

```
                      | 无 L2     | 有 L2     | 多 binding | 空 binding
BUSINESS 单 endpoint  |   T01     |   T02     |    T03     |    T04
QUERY    单 endpoint  |   T05     |   T06     |    -       |    T07
多 endpoint 同 service |   T08     |   T09     |    -       |    -
多 service 一调用     |   T10     |    -      |    -       |    -
service 全空          |   T11     |    -      |    -       |    -
```

---

## 4. 验收标准

### 4.1 必过(P0 阻塞)

| 验收项 | 测法 |
|---|---|
| `pytest tests/plate/test_doc_render.py -v` 12/12 全过 | CI |
| `pytest tests/plate/test_doc_cli.py -v` 7/7 全过 | CI |
| `pytest tests/plate -q` 全量回归 330 + 19 = 349 全过 | CI |
| `python -m Plate.api_doc fin` 输出 Markdown,可肉眼读 | 手动 |
| `import Plate.api_doc` 不触发 `Plate.fin` 自动加载 | 不变量 #1 |
| L2 doc 缺失时静默显示"(无 L2 注释)",不抛错 | test_render §3.1 #4 |

### 4.2 应过(P1 推荐)

| 验收项 | 测法 |
|---|---|
| 渲染输出 git diff 友好(同类端点格式一致) | 手动 + 截图 |
| 输出 < 50 KB(31 端点 L1 only) | `wc -c` |
| 渲染耗时 < 200 ms | `time python -m Plate.api_doc fin` |
| `plate` 命令在 PATH 中 | `which plate` |

### 4.3 可选(P2 nice-to-have)

| 验收项 | 测法 |
|---|---|
| 输出加目录(TOC) | 手动 |
| `--category` / `--path` 过滤参数 | 用法扩展 |
| 多 service 一次渲染到同一文件 | 留 §4.2 Mock server 复用渲染层 |

---

## 5. 风险与缓解

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| `Plate.doc.EndpointDoc` 与 `Plate.api_doc` 命名混淆 | 文档读者混淆 L2 注释 vs API doc 渲染 | 中 | README 显式说明;CLI docstring 区分 |
| L2 doc 永远为空,L1 读者看不到任何人类注释 | dannotations 长期未补 | 低 | doc 渲染时显式显示 "N/M 端点有 L2 注释",提示维护进度 |
| 渲染层无意中 import 触发服务子包加载 | 违反不变承诺 #1 | **高** | `test_zero_invasion` 必过;`Plate.api_doc.__init__` 仅 import `Plate.spec` / `Plate.doc`(L2 数据类),**不** import `Plate.fin` 等服务 |
| Markdown 输出破坏终端 | 用户不重定向到文件 | 低 | 输出纯文本 Markdown,无 ANSI 颜色 |

---

## 6. 文档同步

| 文件 | 改动 |
|---|---|
| `design/phase3/INDEX.md` | 新建,Phase 3 PR 总览(本 PR-3.1 是第一个) |
| `design/PLATE_EVOLUTION.md` §4.1 | "API doc 服务(最先做,成本最低)" 已存在,补 PR-3.1 实现指向 |
| `design/phase2/DECISIONS.md` | 追加 D28:`Plate.api_doc` 命名选择(避开 `Plate.doc` 与 L2 数据类冲突) |
| `README.md` | Phase 2 章节已留空(本会话 PR-2.5 决定),**Phase 3 §4.1 顺手补 Plate 使用入口** |

---

## 7. 决策记录(给 DECISIONS.md)

- **D28**:`Plate.api_doc` 命名(避开 `Plate.doc.EndpointDoc` 数据类命名冲突)
  - 理由:Phase 1 已冻结 `Plate/doc.py` 是 L2 数据类;改成包破坏 A6 向后兼容;语义上
    "api_doc" 比 "doc" 更准确(Markdown 输出,不局限于 L2)
  - 反对意见:有人主张 `Plate/doc/` 子包 → 否,L2 数据类迁移成本高
- **D29**:CLI 入口 `plate doc <service>`,而非 `plate api-doc <service>`
  - 理由:`doc` 是常用命令,与 `git doc` / `cargo doc` 同构;短命令更易记
  - 反对意见:`api-doc` 更明确 → 否,Phase 3 §4.2 mock / §4.3 mcp 都是 `xxx` 命名族,
    不必为 doc 单独特例
- **D30**:渲染层**不缓存** Markdown 产物
  - 理由:31 端点 < 50 KB,渲染 < 100 ms;缓存失效逻辑(L1 变化检测)复杂度不值
  - 反对意见:频繁调应缓存 → 否,API doc 不是热路径

---

## 8. 工作量估计

| 子任务 | 估计 |
|---|---|
| `api_doc/render.py` 实现 | 0.3 PD |
| `api_doc/cli.py` 实现 | 0.2 PD |
| `api_doc/__init__.py` + `__main__.py` | 0.05 PD |
| `pyproject.toml` script | 0.02 PD |
| `test_doc_render.py` 12 tests | 0.2 PD |
| `test_doc_cli.py` 7 tests | 0.15 PD |
| 不变量 #1 验证扩展 | 0.05 PD |
| 文档同步(INDEX/DECISIONS/README) | 0.1 PD |
| 全量回归 + 字节 pin 验证 | 0.05 PD |
| **总计** | **1.12 PD**(PLATE_EVOLUTION §4.1 估的 1 PD 基本一致) |

---

## 9. reviewer 检查清单

| 项 | 检查 |
|---|---|
| 渲染输出正确 | `python -m Plate.api_doc fin` 与 PR-3.1 §2.3 例子格式一致 |
| 单元测试 | `pytest tests/plate/test_doc_render.py -v` 12/12 |
| CLI 测试 | `pytest tests/plate/test_doc_cli.py -v` 7/7 |
| 不变量 | `pytest tests/plate/test_zero_invasion.py -v` 全过(`Plate.api_doc` 加入 allowlist) |
| L1/L2 边界 | `Plate.api_doc.__init__` **不** import 任何 service 子包 |
| 字节 pin | 渲染层纯字符串拼接,不触发 `EndpointSpec.to_dict()`,与字节级 pin 无关 |
| 文档 | DECISIONS.md D28–D30 已记,INDEX.md 已建 |
| 命令行入口 | `pip install -e .` 后 `plate doc fin` 跑通 |

---

## 10. 后续 PR 衔接

- **PR-3.2**:Phase 3 §4.2 Mock server(成本中等)——复用 PR-3.1 渲染层的"读 spec"
  能力,但加 mock_hook / validate_hook 调用
- **PR-3.3**:Phase 3 §4.3 Plate-MCP(成本最高)——把 `render_service` 包成 MCP 工具,
  让 AI skill 直接调;本 PR 末做形态决策:D28 选库形态 vs MCP 形态分立
- **PR-3.4 (可选)**:Phase 3 收口,类比 PR-2.5