"""入站执行参数(params)— 契约校验器 + 槽位写时校验(设计 2026-11-13)。

纯函数、零 DB 依赖(§7-①);路由入口在归属检查后调用
``validate_inbound_params``,场景写侧(create/PUT)调用
``validate_param_slots``。422 ``code``/``fields`` 风格对齐
``runs._reject_inbound_recipe``(方案 §2.3)。

五道闸(顺序固定,首错即抛 —— strict 的缺失清单除外,报完整清单):
1. 场景未声明槽位且带 params → ``param_slot_not_declared``;
2. required 缺失 → ``param_required_missing``;未知键 →
   ``param_not_declared``(完整未知键清单);
3. 逐槽:null → ``param_value_null``;值含 ``${`` →
   ``param_template_forbidden``(**先于类型校验**,fail-closed:值经
   引擎模板展开可把凭证嵌进出站请求 —— 凭证外送面,决策 6)→
   类型 → pattern → 超长;
4. strict(``paramsStrict: true``,决策 7):扫描 steps +
   config.setup/teardown 的 ``${var.*}`` 占位,每个占位须 params
   给值或基线非空 → ``param_placeholder_missing``(完整清单);
5. raw 模式无方案配方可依据,契约校验全部以场景级契约为准 —— 与
   上列同源,无特殊通道(两态同源)。

类型口径与 ``run_prepare.coerce_row_value`` 对齐(虚行通路):number
槽接受原生 JSON 数值与数字串;boolean 槽接受原生布尔与
``"true"/"false"``(大小写不敏感);string 槽只接受字符串。
"""
from __future__ import annotations

import re
from typing import Any

# 保留字虚拟裸方案(决策 3):零存储零迁移,派发器保留字分支;
# 语义 = carry 关闭 + 不取任何方案配方。真实方案 id 是 rs-NNN 命名
# 空间(scheme_store._next_scheme_id),与保留字无冲突。
RAW_SCHEME_ID = "raw"

# 槽位上限 64(与 RunOptions 上限口径同源,设计 §2.1);值长上限由
# 槽位 maxLength 控制(缺省 256,上限 4096)。
MAX_PARAM_SLOTS = 64

_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ParamsError(Exception):
    """422 载荷:code + message + fields(槽位/键名清单)。"""

    def __init__(self, code: str, message: str,
                 fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields or []


# ── 写侧:槽位契约校验(scenario_store create/PUT 双跑)──────────


def validate_param_slots(definition: dict | None,
                         slots: list[dict[str, Any]] | None) -> None:
    """场景写时校验槽位契约(设计 §2.1 / §7-②)。

    - name 形状(1-64,``^[A-Za-z0-9_]+$``)与唯一性、槽位 ≤64:ParamSlot
      pydantic 已钉形状,这里补唯一性与调色板校验;
    - name 必须命中 ``definition.config.vars`` 已声明**标量**键
      (``data_set_store._scalar_vars`` 调色板口径 —— 生成式 spec 变量
      不可指:行覆盖会破坏引擎生成器语义);
    - ``pattern`` 仅 type=string 合法(ParamSlot 模型级校验之外的
      组合约束在此钉)。

    抛 ``ValueError``(scenario_store 写路径错误码前缀约定,
    如 ``scenario_id_exists`` 同款)。
    """
    if not slots:
        return
    if len(slots) > MAX_PARAM_SLOTS:
        raise ValueError(
            f"param_slots_invalid: 槽位数 {len(slots)} 超过上限 {MAX_PARAM_SLOTS}")
    seen: set[str] = set()
    for s in slots:
        name = str(s.get("name") or "")
        if not _NAME_RE.fullmatch(name):
            raise ValueError(
                f"param_slot_name_invalid: 槽位名 {name!r} 须匹配 ^[A-Za-z0-9_]+$ (1-64)")
        if name in seen:
            raise ValueError(
                f"param_slot_name_duplicated: 槽位名重复: {name}")
        seen.add(name)
        if s.get("pattern") and (s.get("type") or "string") != "string":
            raise ValueError(
                f"param_slot_pattern_type: 槽位 {name} 的 pattern 仅 type=string 合法")
    from .data_set_store import _scalar_vars
    # _scalar_vars 吃 draft 容器({"definition": …});这里入参是定义本
    # 体,包一层再喂(调色板口径单源,不另开第二份实现)。
    palette = _scalar_vars({"definition": definition or {}})
    dangling = sorted(seen - palette)
    if dangling:
        raise ValueError(
            "param_slot_var_not_declared: 槽位须命中场景 config.vars 已声明"
            f"的标量键,以下悬空: {', '.join(dangling)}")


# ── 读侧:入站 params 五道闸(路由入口,首错即抛)────────────────


def _slot_type_ok(slot_type: str, value: Any) -> bool:
    """类型闸:与 coerce_row_value 基线还原口径对齐(数字串/布尔串可)。"""
    if slot_type == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.strip())
                return True
            except ValueError:
                return False
        return False
    if slot_type == "boolean":
        if isinstance(value, bool):
            return True
        return (isinstance(value, str)
                and value.strip().lower() in ("true", "false"))
    return isinstance(value, str)


def validate_inbound_params(scenario_payload: dict | None,
                            params: dict[str, Any] | None) -> None:
    """五道闸(设计 §2.3)。``params`` 空 dict / None 等价缺省,直接放行。

    ``scenario_payload`` 是场景行 payload(ScenarioDraft dump):契约
    (paramSlots/paramsStrict)与 definition(steps/config.vars)都从
    这里取 —— 契约自场景行,raw 与真实方案两态同源(闸 5)。
    """
    if not params:
        return
    draft = scenario_payload or {}
    slots_raw = draft.get("paramSlots") or []
    strict = bool(draft.get("paramsStrict"))
    definition = draft.get("definition") or {}

    # 闸 1:未声明契约而带 params → 指引先声明(存量场景行为零变化)
    if not slots_raw:
        raise ParamsError(
            "param_slot_not_declared",
            "场景未声明 paramSlots 契约;请先在场景设置中声明入参槽位"
            "后再携带 params 调用")
    slots = {str(s.get("name")): s for s in slots_raw}

    # 闸 2:required 缺失 / 未知键(完整清单)
    missing = [str(s.get("name")) for s in slots_raw
               if s.get("required") and str(s.get("name")) not in params]
    if missing:
        raise ParamsError(
            "param_required_missing",
            "必填参数缺失: " + ", ".join(sorted(missing)),
            sorted(missing))
    unknown = sorted(k for k in params if k not in slots)
    if unknown:
        raise ParamsError(
            "param_not_declared",
            "未知参数键(不在场景契约内): " + ", ".join(unknown),
            unknown)

    # 闸 3:逐槽 null → 模板 → 类型 → pattern → 超长
    for name in sorted(params):
        value = params[name]
        slot = slots[name]
        if value is None:
            raise ParamsError(
                "param_value_null",
                f"参数 {name} 为 null;要表达空请用空串(与数据集三态语义对齐)",
                [name])
        if isinstance(value, str) and "${" in value:
            # fail-closed(决策 6):不解释、不转义、不降级。JSON \u 转义
            # 在解析期已解码,此处必命中。
            raise ParamsError(
                "param_template_forbidden",
                f"参数 {name} 含模板引用(${{);参数值只允许纯值",
                [name])
        slot_type = str(slot.get("type") or "string")
        if not _slot_type_ok(slot_type, value):
            raise ParamsError(
                "param_type_mismatch",
                f"参数 {name} 类型不符(契约 {slot_type})", [name])
        pattern = slot.get("pattern")
        if pattern and isinstance(value, str):
            try:
                matched = re.fullmatch(pattern, value) is not None
            except re.error as e:
                # 作者侧坏 pattern:按写时已验口径不该到达,防御性拒
                raise ParamsError(
                    "param_pattern_invalid",
                    f"参数 {name} 的契约 pattern 非法: {e}", [name]) from None
            if not matched:
                raise ParamsError(
                    "param_pattern_mismatch",
                    f"参数 {name} 不符合契约 pattern", [name])
        max_len = int(slot.get("maxLength") or 256)
        if isinstance(value, str) and len(value) > max_len:
            raise ParamsError(
                "param_too_long",
                f"参数 {name} 超长(len={len(value)} > {max_len})", [name])

    # 闸 4:strict 占位完备性(决策 7)—— params 给值或基线非空
    if strict:
        from .jsonpath import find_template_var_refs
        refs: set[str] = set()
        config = definition.get("config") or {}
        for node in (definition.get("steps"),
                     config.get("setup"), config.get("teardown")):
            if node:
                refs.update(r for r in find_template_var_refs(
                    node, prefix="var") if r)
        if refs:
            baseline = config.get("vars") or {}
            lack = sorted(
                r for r in refs
                if r not in params and baseline.get(r) in (None, ""))
            if lack:
                raise ParamsError(
                    "param_placeholder_missing",
                    "以下 ${{var.*}} 占位缺值(params 未给且基线为空): "
                    + ", ".join(lack), lack)


def virtual_row(params: dict[str, Any]) -> dict:
    """params → 单虚行(决策 5):走数据集行既有通路,行值即参数值。

    派发段以 ``{"datasetId": None, "rows": [(0, virtual_row(params))]}``
    替代 compute_run_fanout 输出(compose_scenario 行值合入 config.vars,
    行胜于基线、coerce_row_value 类型还原 —— run_prepare.py:455 一行不改)。
    """
    return dict(params)
