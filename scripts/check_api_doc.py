#!/usr/bin/env python
"""平台 API 文档 ↔ openapi 快照 端点级对账守卫(I-04,2026-11-24)。

`docs/PLATFORM-SCENARIO-COMPOSER-API.md` 自我定位是平台侧的权威 API 文档,
但曾长期携带「成节不实」的 `/api/cases` 家族(known-issue
platform-api-doc-false-sections.md,端点级重写 2026-11-24 落地)。本守卫
钉住「文档不再描述不存在的端点」:

* 解析文档中的端点引用(§3 端点总览表行 + §4 详细端点标题);
* 与后端 `contract/openapi.json` 快照(由 `gen_api_contract.py` 从
  `create_app().openapi()` 生成)的方法+路径集比对;
* **文档含快照没有的端点 → 退出 1**(红)—— 这是本守卫的要害:旧端点
  重新进入文档、或新端点写错路径,都在此拦下;
* 快照含文档未提的端点 → 提示(不红)—— 平台还有 executions / auth /
  services 等面,本文档只覆盖场景编排域,不该强求穷举。

用法::

    python scripts/check_api_doc.py            # 对账,红即退出 1
    python scripts/check_api_doc.py --list     # 只打印解析结果不判红

CI:plate-ci「REST 契约守卫」步后一步;pytest 双守卫
`tests/test_api_contract.py::test_platform_api_doc_consistent`。

解析口径(只认两种**表格/标题语境**,避免把退役注里的历史端点误报):
* 表行 `` | `/api/...` | METHOD | ... ``(§3 端点总览);
* 标题 `` ### N.N `METHOD /api/...` ``(§4 详细端点);
带删除线(~~…~~)或行内**退役注记**(❌ / 已退役 / 端点不存在)的行不计。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "PLATFORM-SCENARIO-COMPOSER-API.md"
OPENAPI = REPO / "src" / "gimbal-platform" / "backend" / "contract" / "openapi.json"

# 表行:` | `/api/x` | GET | … |`(§3)。路径与方法各占一列。
_TABLE_ROW = re.compile(r"^\|\s*`(/api/[^`]+)`\s*\|\s*([A-Z]+)\s*\|")
# 标题:`### 4.9 `GET /api/x``(§4)。
_HEADING = re.compile(r"^#{2,4}\s+`([A-Z]+)\s+(/api/[^`]+)`")
# 退役语境:删除线、❌、显式退役词 —— 命中即不计入「文档宣称存在的端点」。
_RETIRED = re.compile(r"~~|❌|已退役|端点不存在|已解散|从未实现")


def _norm_path(path: str) -> str:
    """路径模板归一:参数占位符统一为 `{}` —— 文档写 camelCase
    (`{scenarioId}`),FastAPI/openapi 用函数参数名(`{scenario_id}`),
    语义相同,不得因命名风格误报。"""
    return re.sub(r"\{[^}]+\}", "{}", path)


def doc_endpoints(text: str) -> set[tuple[str, str]]:
    """文档「宣称存在」的 {(method, 归一路径)} —— 表行 + 标题,退役语境不计。"""
    out: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if _RETIRED.search(line):
            continue
        for pat in (_TABLE_ROW, _HEADING):
            m = pat.match(line.strip())
            if m:
                # 表行 group(1)=路径 group(2)=方法;标题 group(1)=方法
                # group(2)=路径 —— 先各取本源,再统一 (METHOD, 归一路径)。
                if pat is _TABLE_ROW:
                    out.add((m.group(2), _norm_path(m.group(1))))
                else:
                    out.add((m.group(1).upper(), _norm_path(m.group(2))))
                break
    return out


def openapi_endpoints() -> set[tuple[str, str]]:
    data = json.loads(OPENAPI.read_text(encoding="utf-8"))
    out: set[tuple[str, str]] = set()
    for path, methods in (data.get("paths") or {}).items():
        for method in methods:
            if method in ("get", "post", "put", "patch", "delete"):
                out.add((method.upper(), _norm_path(path)))
    return out


def main(argv: list[str]) -> int:
    list_only = "--list" in argv
    text = DOC.read_text(encoding="utf-8")
    doc = doc_endpoints(text)
    api = openapi_endpoints()
    if list_only:
        for m, p in sorted(doc):
            mark = "OK " if (m, p) in api else "MISS"
            print(f"{mark}  {m:7} {p}")
        return 0
    # 原样路径用于报错展示(doc 集合存归一路径,这里重解析拿原样)。
    doc_raw: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if _RETIRED.search(line):
            continue
        mt = _TABLE_ROW.match(line.strip())
        if mt:
            doc_raw.add((mt.group(2), mt.group(1)))
            continue
        mh = _HEADING.match(line.strip())
        if mh:
            doc_raw.add((mh.group(1).upper(), mh.group(2)))
    phantom = sorted(doc - api)
    unmentioned = sorted(api - doc)
    if phantom:
        raw_by_norm = {(_m, _norm_path(_p)): _p for _m, _p in doc_raw}
        print(f"check_api_doc: 文档描述了 openapi 快照中不存在的端点({len(phantom)}):")
        for m, p in phantom:
            print(f"  {m:7} {raw_by_norm.get((m, p), p)}")
        print("  —— 平台 API 文档不得描述不存在的端点(known-issue "
              "platform-api-doc-false-sections):按端点级重写或移入退役注记"
              "(行内含「已退役/~~/❌」不计)。")
        return 1
    print(f"check_api_doc: 文档 {len(doc)} 个端点与 openapi 快照一致"
          f"(快照共 {len(api)} 个端点,{len(unmentioned)} 个在本文档场景"
          f"编排域之外,不强求穷举;--list 查看文档侧解析)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
