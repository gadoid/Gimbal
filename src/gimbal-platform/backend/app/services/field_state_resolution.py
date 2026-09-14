"""字段状态解析链(spec 2026-09-05 §3.2)— 所有消费方的单一实现。

``state(path) = step.field_states[path] ?? entry.state ?? 'form'``

消费方(§4):carry_injection 注入面 / carry 路由值表候选面 /
carry_store 漂移检测 / 配置编辑校验(§3.5)。前端表单定面同式实现,
本模块是后端真源 —— 禁止各自散写,改语义只改这里。

输入形状:``declarations`` 为 plate /full wire 的
``request.declarations``(list[dict],条目可带 children 树,M1 起
state 键盖戳);``field_states`` 为 step 顶层的稀疏增量
(``{归一化 path → state}``,§3.1,默认不存)。两者皆防御式:形状
不符按缺席处理(读穿),解析链跑在 dispatch 关键路径上,不抛错。
"""
from __future__ import annotations

from typing import Any, Iterator

# §3.5 软警告词表(备注族)。§9 验收:落户 platform 常量,
# seed 自 plate 政策测试(tests/plate/test_v3_systems_fin.py
# TestCarryStatePolicy 的 DESCRIPTIVE 同款词表,双侧同步维护)。
DESCRIPTIVE = frozenset({"remark", "notes", "cancel_remark"})

VALID_STATES = frozenset({"form", "collapse", "carry"})


def resolve_state(
    path: str, entry_state: Any, field_states: Any,
) -> str:
    """解析链单点实现(§3.2):增量 → 共识默认 → form。

    防御(§3.4 兜底精神):
    * ``field_states`` 形状不符 / 值不在词表 → 该条增量视同缺席
      (读穿;写侧词表约束在配置编辑校验,§3.5);
    * ``entry_state`` 缺席或不在词表 → form(fail-closed:零注入)。
    """
    if isinstance(field_states, dict):
        override = field_states.get(path)
        if override in VALID_STATES:
            return override
    if entry_state in VALID_STATES:
        return entry_state
    return "form"


def iter_flat(declarations: Any) -> Iterator[dict]:
    """children 树先序平铺(容器先于子孙)。

    与 plate ``iter_declarations``(§2.7)次序一致 —— 两侧展开次序
    对齐,注入面/导出面才可对拍。wire 侧防御:非 list / 非 dict 条目
    跳过,不抛错。
    """
    if not isinstance(declarations, list):
        return
    for e in declarations:
        if not isinstance(e, dict):
            continue
        yield e
        yield from iter_flat(e.get("children"))


def _entries(declarations: Any) -> list[dict]:
    return list(iter_flat(declarations))


def carry_entries(declarations: Any, field_states: Any = None) -> list[dict]:
    """解析态 == 'carry' 的条目列表(先序;祖先吸收,见 carry_face)。

    需要完整条目元数据(description/type/enum…)的消费方用 —— 值表
    候选面(routers/carry.py service_fields);只要 {path: type} 的
    注入面用 :func:`carry_face`(本函数之上的薄投影,单一走树逻辑)。
    """
    out: list[dict] = []

    def _walk(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for e in entries:
            if not isinstance(e, dict):
                continue
            path = e.get("path")
            if not isinstance(path, str) or not path:
                continue
            if resolve_state(path, e.get("state"), field_states) == "carry":
                out.append(e)
            else:
                _walk(e.get("children"))

    _walk(declarations)
    return out


def carry_face(declarations: Any, field_states: Any = None) -> dict[str, str]:
    """解析态 == 'carry' 的注入/值表面:{path: 契约类型}。

    **祖先吸收**:carry 容器的子孙不单列 —— 整容器是注入单元(值表
    绑 ``$.supplier`` 整体 JSON 字面量,§4 机制依赖注)。模板子孙
    path 无实例下标,单独注入会物化出错误形态(dict 顶替 array)。
    仅当祖先解析态非 carry 时下钻 —— 承接 form 容器下的 carry 叶子
    (整传一致性 §2.2 只约束 carry 容器 ⇒ 子孙 carry,不反向强制)。

    值表候选面(routers/carry.py service_fields)与漂移检测
    (carry_store.carry_drift)共用本投影的端点级形态
    (``field_states=None`` 读穿:值表是环境级,跟共识默认走,§4)。
    """
    return {str(e["path"]): str(e.get("type") or "string")
            for e in carry_entries(declarations, field_states)}


def composite_states(declarations: Any, field_states: Any = None) -> dict[str, str]:
    """合成态全表(§3.5):{path: 解析态},先序。

    配置编辑校验(树一致性)与前端定面投影的共用输入 —— 校验的对象
    是 plate 默认 + step 增量合并后的合成态,不是裸目录态。
    """
    out: dict[str, str] = {}
    for e in _entries(declarations):
        path = e.get("path")
        if isinstance(path, str) and path:
            out[path] = resolve_state(path, e.get("state"), field_states)
    return out


def catalog_paths(declarations: Any) -> set[str]:
    """目录宇宙(§3.4 交集容忍的参照):树内全部条目 path。"""
    return set(composite_states(declarations))


# ── 配置编辑校验(§3.5;D2/D3 语境继任)────────────────────────────

def _body_template_paths(body: Any) -> set[str]:
    """body 实例路径集合(模板形态:$.a.b,数组下标剥除)—— stale 判定
    的实有参照(2026-09-14 §5.1)。容器自身与叶子都收:提升根($.a 容器)
    与提升叶($.a.b)都应命中。防御:非 dict 读穿为空集。"""
    out: set[str] = set()

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{prefix}.{k}" if prefix != "$" else f"$.{k}"
                out.add(p)
                _walk(v, p)
        elif isinstance(node, list):
            for item in node:
                _walk(item, prefix)

    if isinstance(body, dict):
        _walk(body, "$")
    return out


def validate_field_states(
    declarations: Any, field_states: Any = None, body: Any = None,
) -> dict[str, list[dict]]:
    """合成态校验:plate 默认 + step 增量合并后的树一致性 + 双软警告。

    返回 ``{"errors": [...], "warnings": [...]}``,条目形如
    ``{code, path, message}``;errors 非空 = 拒绝保存(前端门禁),
    warnings 仅提示。校验对象是**合成态** —— 目录里树一致但增量把
    carry 容器的子孙划回 form,同样拒(增量不得破坏整传一致性)。

    * ``tree_inconsistency``(error):carry 容器的子孙解析态非 carry;
    * ``required_carry``(warning):required 条目解析态 == carry
      ("确认值表有兜底,否则请求必挂");
    * ``descriptive_form``(warning):DESCRIPTIVE 词表条目解析态 ==
      form(备注族进渲染面 → 提示,plate 政策建议 carry);
    * ``stale_path``(warning):field_states 含目录外 path 且 body
      无实有(§5.1,2026-09-14:提升字段 = 目录外但 body 实有 → 放行;
      不传 body = 旧行为,全部目录外报 stale)。
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    def _is_descriptive(entry: dict) -> bool:
        name = entry.get("name")
        return isinstance(name, str) and name in DESCRIPTIVE

    def _walk(entries: Any, under_carry: bool) -> None:
        if not isinstance(entries, list):
            return
        for e in entries:
            if not isinstance(e, dict):
                continue
            path = e.get("path")
            if not isinstance(path, str) or not path:
                continue
            rs = resolve_state(path, e.get("state"), field_states)
            if under_carry and rs != "carry":
                errors.append({
                    "code": "tree_inconsistency", "path": path,
                    "message": (
                        f"整传一致性:carry 容器子孙 {path} 合成态为 "
                        f"{rs}(须 carry;增量不得划回)"),
                })
            children = e.get("children")
            if isinstance(children, list) and children:
                _walk(children, under_carry or rs == "carry")
                continue
            # 叶子面规则(容器无值语义,行壳跟 children)
            if rs == "carry" and e.get("required"):
                warnings.append({
                    "code": "required_carry", "path": path,
                    "message": (
                        f"必填字段 {path} 被划出 form 面 —— 确认值表有"
                        f"兜底,否则请求必挂"),
                })
            if rs == "form" and _is_descriptive(e):
                warnings.append({
                    "code": "descriptive_form", "path": path,
                    "message": (
                        f"备注族字段 {path} 进 form 面 —— 政策建议 carry"
                        f"(渲染噪音;值表统一管)"),
                })

    _walk(declarations, False)

    if isinstance(field_states, dict):
        universe = catalog_paths(declarations)
        body_paths = _body_template_paths(body) if body is not None else None
        for path in sorted(set(field_states) - universe):
            if body_paths is not None and path in body_paths:
                continue
            warnings.append({
                "code": "stale_path", "path": path,
                "message": f"目录外 path {path}(plate 目录未声明;已忽略)",
            })

    return {"errors": errors, "warnings": warnings}
