"""契约声明 ↔ 实测响应对账。

契约是**生成**出来的（contract_gen 从平台 OpenAPI 展开），响应是平台**真跑**
出来的。两者会漂，而且漂了没人知道 —— 之前那条评审发现就是这么来的：
漂移检测只校验路由，声明树从来没有任何东西验过。

这道对账回答两个问题：

1. **正向**：生成出来的每条 path，引擎真能在实测响应上求到值吗？
   目录里的 path 是模板态（plate 校验器硬性要求 children 不带 `[i]`），
   这里把它实例化 —— 这一步就是 plate 文档里说的"渲染器实例化"。
2. **反向**：实测响应里有哪些字段，契约压根没声明？
   正向只能证明"写了的能用"，证明不了"该写的都写了" —— 后者才是用例
   作者真正会踩的坑：字段明明在响应里，契约里查不到。

求值器用 **gimbal 自己的 JSONPath**，不另写一套。用例断言最终由引擎求值，
对账换个求值器，结论就不能用来判断断言能不能写。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# gimbal 是同仓兄弟包，不在 bootstrap 的依赖里（它只声明 pyyaml）。
# 用相对路径挂上 src/，让对账器用引擎的求值器而不是自己糊一个。
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gimbal.utils.jsonpath import get  # noqa: E402


@dataclass
class Report:
    """一次对账的结论。四个集合互斥，覆盖全部已声明 path 与实测叶子。"""

    hits: set[str] = field(default_factory=set)
    misses: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)
    unevaluable: list[str] = field(default_factory=list)
    undeclared: list[str] = field(default_factory=list)
    dynamic_keys: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.misses or self.unevaluable or self.undeclared)

    def summary(self) -> str:
        return (
            f"命中 {len(self.hits)} / 落空 {len(self.misses)} / "
            f"空集合未验证 {len(self.unverifiable)} / "
            f"引擎求值失败 {len(self.unevaluable)} / "
            f"响应有契约无 {len(self.undeclared)} / "
            f"动态 map 键 {len(self.dynamic_keys)}"
        )


def _opaque_objects(decls: list[dict], here: str = "$", out: set[str] | None = None) -> set[str]:
    """收集「声明了自己、却没有 children」的 object 路径。

    这类容器在 OpenAPI 里是 `additionalProperties: {type: X}` —— 平台给了
    值类型，但**键是运行时决定的**（`ActivityOut.sources` 当初有
    adaptations/executions/scenarios 三个域，将来有什么取决于跑过什么）。
    契约穷举不了，它下面的直接子键因此不是缺口。

    判据是「有没有 children」而不是「父路径在不在契约里」：后者会把
    `$.items[0].meta.surprise` 这种真缺口也误判成动态键。
    """
    out = set() if out is None else out
    for d in decls or []:
        name = d.get("name") or ""
        if not name:
            continue
        path = f"{here}.{name}"
        dtype = d.get("type") or ""
        kids = d.get("children") or []
        if dtype == "object" and not kids:
            out.add(path)
            continue
        if kids:
            _opaque_objects(
                kids, f"{path}[0]" if dtype == "array" else path, out,
            )
    return out


def instantiable_paths(
    decls: list[dict],
    *,
    here: str = "$",
    guards: tuple[str, ...] = (),
) -> Iterator[tuple[str, str, tuple[str, ...]]]:
    """声明树 → (实例化 path, type, 祖先数组守卫) 流。

    模板态 → 实例化的唯一规则：**array 节点的下一层插 `[0]`**，object 节点
    原样下沉。目录里不带下标是 plate 的硬性纪律（`_check_declarations` ③），
    实例下标本就是渲染器的活。

    声明条目自带的 `path` 是模板态（生成器直接写进 JSON 的），只用于识别
    条目；对外的实例化 path 一律由 `here` + name 沿树累积得出 —— 两处
    各自维护一份路径，迟早有一处对不上。

    守卫记录了该条目依赖的祖先数组路径 —— 祖先数组为空时，条目落空与否
    无从判定，混进 misses 会让每个带列表的端点报一堆假警报。
    """
    for d in decls or []:
        name = d.get("name") or ""
        if not name:
            continue
        path = f"{here}.{name}"
        dtype = d.get("type") or ""
        yield (path, dtype, guards)
        kids = d.get("children") or []
        if not kids:
            continue
        if dtype == "array":
            yield from instantiable_paths(
                kids, here=f"{path}[0]", guards=(*guards, path),
            )
        else:
            yield from instantiable_paths(kids, here=path, guards=guards)


def walk_response_paths(doc: Any, prefix: str = "$") -> Iterator[str]:
    """响应 JSON → 全部标量叶子 path（容器本身不产出）。

    对账的是字段，不是容器 —— 容器永远"存在"，比对它没有信息量。
    """
    if isinstance(doc, dict):
        for k, v in doc.items():
            yield from walk_response_paths(v, f"{prefix}.{k}")
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from walk_response_paths(v, f"{prefix}[{i}]")
    else:
        yield prefix


def _is_empty_array(doc: Any, path: str) -> bool:
    try:
        v = get(doc, path)
    except Exception:  # noqa: BLE001 — 守卫问不到就当不是空数组
        return False
    return isinstance(v, list) and not v


# 响应侧路径归一化用的两把尺：
# _INDEX 折行（契约只对首行建模），_TAIL_INDEX 认集合元素（契约声明容器，不声明
# 它的第 1、2、3 个元素）。
_INDEX = re.compile(r"\[\d+\]")
_TAIL_INDEX = re.compile(r"\[\d+\]$")


def _fold_response_path(path: str, *, root_is_array: bool) -> str | None:
    """响应侧叶子 path → 可与契约 path 比对的形态。

    三步归一化，顺序不能换：
    1. **丢集合元素** —— 以 `[N]` 结尾的是集合里的一个值（`tags[1]`）。
       契约声明的是 `tags` 容器，集合长度随数据变，逐个元素算缺口是假警报。
    2. **折行** —— 其余下标一律折成 `[0]`。契约的 children 是模板态，实例
       化只取首行；响应有 11 行不代表契约缺 10 行。
    3. **拆根下标** —— 响应本身是数组时（`GET /api/data-sets`），契约把元素
       字段提到了顶层，响应侧的 `$[0].x` 要还原成 `$.x`。
    """
    if _TAIL_INDEX.search(path):
        return None
    folded = _INDEX.sub("[0]", path)
    if root_is_array and folded.startswith("$[0]."):
        folded = "$." + folded[len("$[0]."):]
    return folded


def reconcile(decls: list[dict], response: Any) -> Report:
    """声明树 + 实测响应 → 对账报告。

    响应本身是数组时（`GET /api/data-sets` 这类），契约把元素字段提到了
    顶层（`$.datasetId`），求值时得落到第一行 —— 否则每个字段都误判成落空，
    而实际全都能取到。
    """
    report = Report()
    root_is_array = isinstance(response, list)
    declared: set[str] = set()

    for path, _dtype, guards in instantiable_paths(decls):
        declared.add(path)
        eval_path = f"$[0]{path[1:]}" if root_is_array else path
        try:
            value = get(response, eval_path)
        except Exception:  # noqa: BLE001 — 引擎不认这个 path，不该让整份报告没了
            report.unevaluable.append(path)
            continue
        if value is not None:
            report.hits.add(path)
        elif any(_is_empty_array(response, g) for g in guards):
            report.unverifiable.append(path)
        else:
            report.misses.append(path)

    leaves = {
        folded
        for folded in (
            _fold_response_path(p, root_is_array=root_is_array)
            for p in walk_response_paths(response)
        )
        if folded is not None
    }
    report.undeclared = sorted(leaves - declared)
    if report.undeclared:
        opaque = _opaque_objects(decls)
        gaps: list[str] = []
        for path in report.undeclared:
            parent = path.rsplit(".", 1)[0] if "." in path[2:] else None
            (report.dynamic_keys if parent in opaque else gaps).append(path)
        report.dynamic_keys.sort()
        report.undeclared = gaps
    return report
