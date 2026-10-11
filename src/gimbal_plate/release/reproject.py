"""call 按修订重投影（Release v4.4 §4.5；开发计划 T1.8 / RS2）。

``/convert`` 按 ``meta.plate`` 的**原值**取修订——平台入队时已解析生效
修订并写入执行副本（解析只在一处发生，4.4/4.5），本模块只做合并：

- **binding 派生字段取投影**（protocol / method / path / timeout / headers）；
- **场景自有字段取存储**（service 引用、user、path_params、追加 headers
  及其他协议自有字段）；
- 追加 header 与投影 binding headers 同名 → ``header_conflicts_binding``；
- 存储中出现 binding 派生字段 → ``binding_field_in_storage``（M4 生效后
  场景只存场景自有字段，Release 6.2；过渡期平台不带 ``meta.plate``，
  不走本路径）；
- 系统未声明 → ``version_undeclared``；修订不存在 → ``release_not_found``；
  修订中没有该接口 → ``endpoint_not_in_release``。

端点锚点（M3 过渡口径）：优先 ``step.endpoint``（M3 生效后），否则
``step.call.view_hints.endpoint_id``（平台现状锚点）；重投影后两者剥离。
没有锚点的步骤（手写原始调用）原样使用存储的 call（4.5）。
"""
from __future__ import annotations

from typing import Any

_BINDING_FIELDS = ("protocol", "method", "path", "timeout", "headers")
# 存储禁带的派生字段：headers 除外——存储的 headers 是场景自有的
# 「追加 headers」（4.5），与投影的 binding headers 合并、同名即冲突。
_STORAGE_FORBIDDEN = ("protocol", "method", "path", "timeout")


class ReprojectError(Exception):
    """重投影错误：code 即 HTTP 错误码。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _merge_call(stored: dict[str, Any], proj: dict[str, Any],
                endpoint_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    own = {k: v for k, v in stored.items()
           if k not in ("kind", "view_hints")}
    bad = [k for k in _STORAGE_FORBIDDEN if k in own]
    if bad:
        raise ReprojectError(
            "binding_field_in_storage",
            f"{endpoint_id}: 存储 call 含 binding 派生字段 {bad}"
            "——场景只存场景自有字段(Release 6.2),派生字段由投影提供")
    for k in _BINDING_FIELDS:
        if k in proj:
            out[k] = proj[k]
    proj_headers = dict(proj.get("headers") or {})
    stored_headers = dict(own.pop("headers", None) or {})
    clash = sorted(set(proj_headers) & set(stored_headers))
    if clash:
        raise ReprojectError(
            "header_conflicts_binding",
            f"{endpoint_id}: 追加 header 与 binding headers 同名: {clash}")
    if proj_headers or stored_headers:
        out["headers"] = {**proj_headers, **stored_headers}
    out.update(own)      # service / user / path_params / 协议自有字段
    return out


def reproject_raw(
    raw_scenario: dict[str, Any],
    meta_plate: dict[str, Any] | None,
    *,
    root: Any,
    working_registry: Any = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """dict 层重投影（validate 之前：合并产物才是被校验的最终形态）。

    返回 ``(新 scenario dict, 实际使用的修订表)``；``used`` 即 4.5 的
    「响应带回实际使用的修订表」（working 声明原样回 working）。
    """
    from gimbal_plate.release import read as release_read

    snaps: dict[str, Any] = {}
    used: dict[str, str] = {}
    for system, ref in (meta_plate or {}).items():
        ref = str(ref)
        if ref == "working":
            snaps[system] = None
            used[system] = "working"
            continue
        line, n, _m = release_read.resolve_revision(root, system, ref)
        snaps[system] = release_read.load_snapshot(root, system, line, n)
        used[system] = f"{line}#{n}"

    def _projection_for(endpoint_id: str) -> dict[str, Any]:
        system = endpoint_id.split(".")[0]
        if system not in snaps:
            raise ReprojectError(
                "version_undeclared",
                f"{endpoint_id}: 所属系统 {system!r} 未在 meta.plate 中声明")
        snap = snaps[system]
        if snap is None:                       # 声明 working → 当前树
            if working_registry is not None:
                spec = working_registry.index_for("endpoint")
                item = spec.index.get(endpoint_id) if spec else None
                if item is not None:
                    from gimbal_plate.release.release import _call_projection
                    return _call_projection(item)
            raise ReprojectError(
                "endpoint_not_in_release",
                f"{endpoint_id}: 不在 working 注册表中")
        proj = snap.projections.get(endpoint_id)
        if proj is None:
            raise ReprojectError(
                "endpoint_not_in_release",
                f"{endpoint_id}: 不在修订 {used[system]} 中")
        return proj

    raw = dict(raw_scenario)
    steps_out: list[Any] = []
    for step in raw.get("steps") or []:
        if not isinstance(step, dict):
            steps_out.append(step)
            continue
        call = step.get("call") or {}
        vh = call.get("view_hints") or {}
        endpoint_id = step.get("endpoint") or vh.get("endpoint_id")
        if not endpoint_id:
            steps_out.append(step)             # 手写原始调用,原样使用
            continue
        proj = _projection_for(str(endpoint_id))
        new_call = _merge_call(dict(call), proj, str(endpoint_id))
        new_step = {k: v for k, v in step.items() if k != "endpoint"}
        new_step["call"] = new_call
        steps_out.append(new_step)
    raw["steps"] = steps_out
    return raw, used


__all__ = ["ReprojectError", "reproject_raw"]
