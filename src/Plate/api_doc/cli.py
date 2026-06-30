"""``plate doc`` CLI 入口(Phase 3 §4.1)。

对应设计:``design/phase3/PR-3.1.md`` §2.4。

调用方式:

    # 装包后
    plate doc fin

    # 或不装包直接跑
    python -m Plate.api_doc fin

行为:
    - 接收一个或多个 service 名作位置参数
    - 对每个 service 调 ``registry.warm([svc])`` 拉式收集 EndpointSpec
    - 调 ``Plate.api_doc.render.render_service`` 输出 Markdown 到 stdout
    - 多个 service 间用 ``\\n---\\n`` 分隔
    - service 缺失 / 解析失败 → stderr 警告 + exit code 非 0

L2 lookup 工厂:Phase 3 §4.1 只支持 fin(``Plate.fin.dannotations.get_doc``)。
未登记的 service 输出时 ``doc_lookup=None``,所有 endpoint 显示 "(无 L2 注释)"。
扩展方式:在 ``_DOC_LOOKUP_FACTORIES`` 加一行即可,渲染层无改动。

退出码:
    0  全部 service 成功渲染
    1  部分 service 失败(至少一个成功渲染)
    2  全部 service 失败 / 参数错误
"""
from __future__ import annotations

import importlib
import sys
from typing import Callable

from Plate import registry
from Plate.api_doc.render import render_service
from Plate.doc import EndpointDoc


# ════════════════════════════════════════════════════════════════════════════
# I/O 编码(Windows console 默认 cp936,强制 stdout/stderr UTF-8 防乱码)
# ════════════════════════════════════════════════════════════════════════════

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


# ════════════════════════════════════════════════════════════════════════════
# L2 lookup 工厂
# ════════════════════════════════════════════════════════════════════════════

# service 名 → L2 doc 查询函数 的工厂映射。
# 未登记的 service 输出时 ``doc_lookup=None``,所有 endpoint 显示 "(无 L2 注释)"。
#
# 新 service 接入方式:在 ``Plate.<svc>.dannotations`` 模块里实现 ``get_doc(path)``,
# 然后在本字典加一行 ``"<svc>": lambda: lazy_import("<svc>")``。
_DOC_LOOKUP_FACTORIES: dict[str, Callable[[], Callable[[str], EndpointDoc | None]]] = {
    "fin": lambda: _lazy_get_doc("fin"),
}


def _lazy_get_doc(service: str) -> Callable[[str], EndpointDoc | None]:
    """延迟 import L2 lookup,避免顶层 import 触发 service 子包加载(不变量 #1)。"""
    module = importlib.import_module(f"Plate.{service}.dannotations")
    return module.get_doc


# ════════════════════════════════════════════════════════════════════════════
# CLI main
# ════════════════════════════════════════════════════════════════════════════


_USAGE = """\
plate doc — 渲染 Plate 服务的 Markdown API 文档(Phase 3 §4.1)

用法:
    plate doc <service> [<service> ...]
    python -m Plate.api_doc <service> [<service> ...]

示例:
    plate doc fin
    plate doc fin foo   # foo 未登记 → 仅 fin 渲染,foo 跳过 + stderr 警告

选项:
    -h / --help    显示本帮助
"""


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。返回 process exit code。"""
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(_USAGE)
        return 0

    services = argv

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
            print(
                f"[plate doc] service '{svc}' 已 collect 但无 spec,跳过",
                file=sys.stderr,
            )
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

    # 退出码策略:与 POSIX 工具一致——全部成功 0,部分失败 1,全部失败 2。
    if failed_services and not success_services:
        return 2
    if failed_services or skipped_services:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())