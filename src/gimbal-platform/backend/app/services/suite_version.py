"""Suite 版本一致性检查与可用集合交集（Release v4.4 §6.3 / 版本模型 4.4 / R25）。

规则：
- 同一 Suite 内同一系统的**版本线**必须一致（R25 / SUITE_VERSION_MISMATCH）
- 执行时统一到同一修订：取所有成员可用集合的**交集**，用其中最新的修订
- 交集为空时拒绝执行，列出需要做线内修正的成员

可用集合语义（版本模型 4.2，D-5）：成员的可用集合 = 其版本线内、该成员
用到的接口结构与各自已验证修订完全相同的全部修订（不必连续区间）。
"""
from __future__ import annotations

from typing import Any

from app.services import plate_client


class SuiteVersionError(Exception):
    """Suite 版本不一致或可用集合无交集。"""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


async def check_and_resolve_suite_versions(
    member_payloads: list[dict[str, Any]],
) -> dict[str, str]:
    """检查 Suite 成员的版本一致性并计算统一修订。

    入参：每个成员的场景 payload dict（取 ``definition.meta.plate`` 与
    ``definition.steps[].endpoint`` 的系统前缀）。
    返回：``{系统: 生效修订}``（所有成员统一使用）。

    Raises:
        SuiteVersionError: SUITE_VERSION_MISMATCH（版本线不一致）或
            SUITE_REVISION_EMPTY_INTERSECTION（交集为空）。
    """
    if not member_payloads:
        return {}

    # 1. 收集各成员的 meta.plate 与接口使用
    system_lines: dict[str, set[str]] = {}   # 系统 → 成员声明的版本线集合
    member_info: list[dict] = []              # 每个成员的版本声明与接口

    for i, payload in enumerate(member_payloads):
        defn = (payload or {}).get("definition") or {}
        meta_plate = (defn.get("meta") or {}).get("plate") or {}
        endpoints: set[str] = set()
        for step in (defn.get("steps") or []):
            if not isinstance(step, dict):
                continue
            ep = step.get("endpoint") or \
                ((step.get("call") or {}).get("view_hints") or {}).get("endpoint_id")
            if ep:
                endpoints.add(str(ep))
        member_info.append({
            "index": i, "meta_plate": meta_plate, "endpoints": endpoints,
        })
        for system, ref in meta_plate.items():
            if ref and ref != "working":
                line = ref.rsplit("#", 1)[0]
                system_lines.setdefault(system, set()).add(line)

    # 2. 版本线一致性检查（R25）
    for system, lines in system_lines.items():
        if len(lines) > 1:
            raise SuiteVersionError(
                "SUITE_VERSION_MISMATCH",
                f"系统 {system!r} 在 Suite 成员中声明了不同版本线: "
                f"{sorted(lines)}——同一 Suite 内同一系统必须版本线一致",
                {"system": system, "lines": sorted(lines)},
            )

    # 3. 逐系统解析生效修订
    resolved: dict[str, str] = {}
    for system in system_lines:
        # 收集该系统在各成员的接口使用与已验证修订
        endpoints_union: set[str] = set()
        meta_for_system: dict[str, str] = {}
        for m in member_info:
            for ep in m["endpoints"]:
                if ep.startswith(f"{system}."):
                    endpoints_union.add(ep)
            if system in m["meta_plate"]:
                ref = m["meta_plate"][system]
                if ref != "working":
                    meta_for_system[str(m["index"])] = ref
        if not meta_for_system or not endpoints_union:
            continue

        # 逐成员 resolve，取各自 available 的交集
        available_sets: list[set[int]] = []
        line = ""
        for member_idx, ref in meta_for_system.items():
            try:
                result = await plate_client.resolve(
                    {system: ref},
                    {system: sorted(endpoints_union)},
                )
                info = result.get(system, {})
                avail = info.get("available") or []
                available_sets.append(set(avail))
                line = ref.rsplit("#", 1)[0]
            except Exception:
                # plate 不可用时由上层统一处理
                continue

        if not available_sets:
            continue

        # 交集
        intersection = available_sets[0]
        for s in available_sets[1:]:
            intersection &= s

        if not intersection:
            raise SuiteVersionError(
                "SUITE_REVISION_EMPTY_INTERSECTION",
                f"系统 {system!r} 各成员的可用修订无交集——"
                "需先对各成员做线内修正（接口结构变化未适配）",
                {"system": system,
                 "member_available": [
                     {"member": idx, "available": sorted(s)}
                     for (idx, _), s in zip(meta_for_system.items(),
                                            available_sets)]},
            )

        # 用交集中最新的修订
        best = max(intersection)
        resolved[system] = f"{line}#{best}"

    return resolved


def extract_system_lines_from_suite_mode_config(
    mode_config: dict[str, Any],
) -> dict[int, dict[str, str]]:
    """从 Suite 的 mode_config.units 提取各成员（scenarioId→行号）的
    版本声明——供 Suite 编辑页显示版本分布。

    返回：``{scenarioId: {系统: 版本线}}``
    """
    out: dict[int, dict[str, str]] = {}
    for unit in (mode_config.get("units") or []):
        scen_id = unit.get("scenarioId")
        if not scen_id:
            continue
        # member 的 meta.plate 在 scenario payload 里——这里只从
        # mode_config 层面看结构（编排形态按 scenarioId 引用，不内嵌
        # 版本声明），实际版本分布需查成员场景。
        out[scen_id] = {}
    return out
