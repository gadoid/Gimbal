"""plate 侧已落地的 py 契约定义 ↔ 平台 OpenAPI 的结构对账（常驻门）。

契约定义从一份 358KB 的 `endpoints.json` 换成了 123 个 fin 形制的 py 文件
之后，「JSON 是真源」这个不变量没了 —— 少了一个可以整体 diff 的产物。门补上
它，而且是**逐字段**补的：漂移检测（test_contract_drift）只验路由，这里验
声明树。

方向是**单向**（生成的 ⊆ 已声明的），理由与漂移检测一致：

- 端点文件是给人改的 —— 人工核订的 description / ui_kind / required 都不在
  OpenAPI 里，所以「多了」是正常的，不算漂移；
- 「少了」才算：声明过的字段从定义里消失，用例作者照着旧文档写的断言会挂，
  而门是唯一能发现这件事的东西。

真打平台核对响应字段面的那道门在 test_contract_reconcile_live.py。这道门
不碰网络，跑的是「重新生成一遍，与磁盘上已提交的相比有没有掉东西」。
"""

from __future__ import annotations

import pytest

from gimbal_bootstrap.contract_gen import build_specs, fetch_openapi

# 平台里没进契约的 4 个端点（service-profiles / user-preferences /
# catalog-strategies / run-schemes）—— 契约是地板不是天花板，不算缺口。
# 反过来它们也不参与本门:门只检查「生成了但没落地」的字段。


@pytest.fixture(scope="module")
def generated() -> dict[str, dict]:
    return {spec["id"]: spec for spec in build_specs(fetch_openapi(allow_inprocess_fallback=True))[0]}


@pytest.fixture(scope="module")
def installed() -> dict:
    from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS

    return {ep.id: ep for ep in ALL_ENDPOINTS}


def _dict_paths(decls: list[dict], out: set[str] | None = None) -> set[str]:
    """中间形态的声明树 → 模板态 path 集合（测试侧自带展开，不依赖被测实现）。"""
    out = set() if out is None else out
    for d in decls:
        out.add(d["path"])
        _dict_paths(d.get("children") or [], out)
    return out


def _spec_paths(decls) -> set[str]:
    from gimbal_plate.schema.endpoint.io_spec import iter_declarations

    return {d.path for d in iter_declarations(decls)}


def test_every_generated_field_is_still_declared_in_the_py_definitions(generated, installed):
    """生成器展开出的每个字段，都得在已落地的 py 定义里还在。

    少一个就是一个「用例作者按老文档写了断言、跑起来挂掉」的坑 —— 而且是静默的：
    契约少声明一个字段，用例照样能建，只是那条断言永远落空。
    """
    missing: list[str] = []
    for eid, spec in generated.items():
        ep = installed.get(eid)
        if ep is None:
            missing.append(f"{eid}: 契约里有这个端点，plate 的定义里没有")
            continue
        for status, r in spec["responses"].items():
            want = _dict_paths(r["declarations"])
            got = _spec_paths(ep.responses[int(status)].declarations)
            dropped = sorted(want - got)
            if dropped:
                missing.append(f"{eid} {status} 少了 {len(dropped)} 个字段: {dropped[:5]}")
        want = _dict_paths(spec["request"]["declarations"])
        got = _spec_paths(ep.request.declarations)
        if want - got:
            missing.append(f"{eid} request 少了 {sorted(want - got)[:5]}")
    assert not missing, "py 契约定义与重新生成的结果不一致：\n" + "\n".join(missing)


def test_every_definition_file_is_syntactically_valid():
    """产物是 123 个 py 文件，任何一个写坏了都只会在 plate 启动时炸。

    平台字段面会随后端演进（描述里带引号、超长、字段名带连字符），生成器
    对这些的转义没有测试覆盖 —— 用真实 OpenAPI 全量 compile 一遍，坏在生成
    期而不是 plate 启动期。
    """
    import pathlib

    import gimbal_plate.systems.platform.endpoint as pkg

    root = pathlib.Path(pkg.__file__).parent
    files = sorted(root.rglob("*.py"))
    assert len(files) > 100, f"只找到 {len(files)} 个定义文件，生成器多半没跑全"
    broken = []
    for f in files:
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as exc:
            broken.append(f"{f.relative_to(root)}:{exc.lineno} {exc.msg}")
    assert not broken, "契约定义文件语法错误：\n" + "\n".join(broken)


def test_no_definition_file_is_orphaned(generated):
    """磁盘上的端点文件必须都在聚合层的导入清单里。

    生成器只写不删：平台下掉一个路由再重新生成，那个 .py 会永远留在包里 ——
    语法有效、能 import，却没人注册它，也不会让任何测试变红。端点文件多到
    123 个时，人是不会发现少了一个、少了一个的。
    """
    import pathlib
    import re

    import gimbal_plate.systems.platform.endpoint as pkg

    root = pathlib.Path(pkg.__file__).parent
    agg = (root / "__init__.py").read_text(encoding="utf-8")
    imported = set(
        re.findall(r"from gimbal_plate\.systems\.platform\.endpoint\.([\w.]+) import", agg)
    )
    on_disk = {
        ".".join(f.relative_to(root).with_suffix("").parts)
        for f in root.rglob("*.py")
        if f.name != "__init__.py" and f.parent != root
    }
    assert not on_disk - imported, (
        "这些端点文件没被聚合层导入（平台已无对应路由？确认后手工删除）：\n"
        + "\n".join(f"  {p}" for p in sorted(on_disk - imported))
    )
    assert not imported - on_disk, (
        "聚合层导入了磁盘上不存在的模块（plate 启动会 ImportError）：\n"
        + "\n".join(f"  {p}" for p in sorted(imported - on_disk))
    )


def test_the_py_definitions_carry_more_than_the_generator_ever_writes(installed):
    """反向防呆：门不能因为「两边都空」而空转。

    上一条门若退化成「什么都不查」，这里会响 —— 定义里必须真有下钻出来的
    children，而不是一层一级桩。
    """
    nested = sum(
        len(d.children or [])
        for ep in installed.values()
        for r in ep.responses.values()
        for d in r.declarations
    )
    assert len(installed) > 100, f"定义只剩 {len(installed)} 条端点，生成器多半坏了"
    assert nested > 200, f"带下级结构的声明只剩 {nested} 条，下钻多半退化了"
