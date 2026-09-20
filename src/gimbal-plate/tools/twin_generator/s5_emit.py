"""S5:装订 —— EndpointSpec Python 源码渲染 + 碰撞跳过(手建优先)+ 对照报告。"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .ir import ActionIR, FieldIR
from .s2c_frontend import FE_TYPE_MAP

_HEADER = '''"""{id} —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: {baseline} | 生成时间: {now}
needs_capture(首跑经 gimbal 执行回填): {nc}
溯源统计: {provenance}
"""
'''

_TEMPLATE = '''from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
    ValueSource,
)

{const}: Final[EndpointSpec] = EndpointSpec(
    id={id!r},
    system='fin',
    service='fin-service',
    name={zh!r},
    description={zh!r} + ' [generated:{baseline}]',
    api=ApiSpec(
        service='fin-service',
        method={method!r},
        path={path!r},
        headers={{}},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
{entries}
        ],
    ),
    responses={{
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[{envelope}
            ],
        ),
    }},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
'''


def _render_state(f: FieldIR) -> str:
    """只读 S4 赋值(state 判据真源在 state_rules.py,装订侧不再复述)。"""
    return f.state


def _ui_kind(f: FieldIR) -> str:
    """T5.1:FE high fe_type 采信 > enum→select > 数值/布尔 >
    _file 后缀 → file > text 列 → textarea > text;容器 → unknown。"""
    if f.container:
        return "unknown"
    if f.fe_confidence == "high" and f.fe_type:
        return FE_TYPE_MAP.get(f.fe_type, "text")
    if f.enum_values:
        return "select"
    if f.type_ in ("integer", "number"):
        return "number"
    if f.type_ == "boolean":
        return "boolean"
    if f.key.endswith(("_file", "_file_list")):
        return "file"
    if f.col_type.split("(")[0] in ("text", "mediumtext", "longtext"):
        return "textarea"
    return "text"


# T5.4:响应信封(全端点统一;Api 回调模块 retCode/retMsg)。
# data 行形状不碰(行为面归场景用例 —— 用户裁决 2026-09-20)。
_ENVELOPE = '''
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),
'''

_ENVELOPE_API = '''
            DeclarationEntry(name='retCode', path='$.retCode', type='number',
                             required=False, ui_kind='number',
                             description='回调状态码(0=成功)', assertable=True),
            DeclarationEntry(name='retMsg', path='$.retMsg', type='string',
                             required=False, ui_kind='text',
                             description='回调提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
'''


def _safe_name(key: str) -> str:
    """D1:name 须为 ASCII 标识符。个别规则键带点(param.save_path)→
    下划线化;path 保留原键(寻址真源是 path)。"""
    return re.sub(r"\W", "_", key, flags=re.ASCII) if not key.isidentifier() \
        else key


def _entry_lines(fields: list[FieldIR], prefix: str = "") -> str:
    """prefix:容器子孙的 path 前缀(模板态 $.<container>.<child>)。"""
    lines = []
    for f in fields:
        kwargs = [f"name={_safe_name(f.key)!r}", f"path=f'$.{prefix}{f.key}'",
                  f"type={f.type_!r}", f"state={_render_state(f)!r}",
                  f"ui_kind={_ui_kind(f)!r}"]
        if f.required:
            kwargs.append("required=True")
        # enum 一致性(io_spec 构造期):default 须 ∈ enum,冲突则弃 default 保 enum
        if f.default is not None and (not f.enum_values or f.default in f.enum_values):
            kwargs.append(f"default={f.default!r}")
        # T5.2:example 取 FE payload 字面量值(仅 high 置信)
        if f.example and f.fe_confidence == "high":
            kwargs.append(f"example={f.example!r}")
        if f.zh:
            kwargs.append(f"description={f.zh!r}")
        if f.enum_values:
            # §3.3③ enum × value_source 互斥:enum 优先(S4 同判),value_source 弃挂
            kwargs.append(f"enum={f.enum_values!r}")
        elif f.value_source:
            # T5.5:value_source 挂上 → lookup
            kwargs.append(
                f"value_source=ValueSource(view={f.value_source[0]!r}, "
                f"column={f.value_source[1]!r}), source_kind='lookup'")
        line = f"            DeclarationEntry({', '.join(kwargs)}"
        if f.container and f.children:
            # T5.3 行容器:children 模板态(path 无 [i],实例化归渲染器)
            inner = _indent(_entry_lines(f.children, prefix=f.key + "."), "    ")
            line += f",\n                children=[\n{inner}\n                ]"
        line += "),"
        if f.flags:
            line += "  # " + ", ".join(f.flags)
        lines.append(line)
    return "\n".join(lines) or "            # (无字段 — 键面为空)"


def _indent(text: str, pad: str) -> str:
    return "\n".join(pad + ln if ln.strip() else ln for ln in text.splitlines())


def render_endpoint(act: ActionIR, fields: list[FieldIR], baseline: str) -> str:
    nc = [f.key for f in fields if f.flags] or ["(无)"]
    # T5.5 溯源统计:zh 来源分布(空 → 无zh 桶)+ fe 置信/enum 挂载计数
    prov = Counter(f.zh_source or "无zh" for f in fields)
    prov_line = ", ".join(f"{k}={v}" for k, v in
                          sorted(prov.items(), key=lambda kv: -kv[1]))
    prov_line += (f" | fe_high={sum(1 for f in fields if f.fe_confidence == 'high')}"
                  f", enum={sum(1 for f in fields if f.enum_values)}")
    zh = next((f.zh for f in fields if f.key == "action" and f.zh),
              f"{act.controller}.{act.action}")
    head = _HEADER.format(id=act.id, baseline=baseline,
                          now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          nc=", ".join(nc), provenance=prov_line)
    body = _TEMPLATE.format(
        const=act.const_name, id=act.id, zh=zh, baseline=baseline,
        method=act.method, path=act.path, entries=_entry_lines(fields),
        envelope=_ENVELOPE_API if act.module == "Api" else _ENVELOPE)
    return head + body


def emit_all(actions: list[ActionIR], all_fields: dict, out_dir: Path,
             existing_ids: set[str], baseline: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    emitted = skipped = nc_total = 0
    for act in actions:
        if act.id in existing_ids:
            skipped += 1
            continue
        fields = all_fields.get(act.id, [])
        nc_total += sum(1 for f in fields if f.flags)
        fname = f"{act.module.lower()}_{act.const_name.lower()}.py"
        (out_dir / fname).write_text(
            render_endpoint(act, fields, baseline), encoding="utf-8")
        emitted += 1
    return {"emitted": emitted, "skipped": skipped,
            "needs_capture": nc_total}


def compare_faces(all_fields: dict, handbuilt: dict,
                  evidence: dict | None = None) -> str:
    """三分类差异报告:missing(分档)/extra(生成多)/diff(同键字段异)。

    missing 分档(T6.1):[FE] 前端面有证据而漏(真漏,生成器 bug)/
    [BE] Lang/header/CSV 次级源可达而未入键集(键集判据不含这些源)/
    [capture] 无静态源(首跑回填豁免,不计败)。
    evidence:ep_id → (fe_keys, be_keys);缺省时全部落 [capture]。
    """
    evidence = evidence or {}
    lines = ["# 对照报告(生成 vs 手建 ground truth)", ""]
    for ep_id, hb_keys in sorted(handbuilt.items()):
        gen = {f.key: f for f in all_fields.get(ep_id, [])}
        fe_keys, be_keys = evidence.get(ep_id, (set(), set()))
        missing = [k for k in hb_keys if k not in gen]
        extra = [k for k in gen if k not in hb_keys]
        diffs = []
        for k, (state, zh, enum, required, vs, ui) in hb_keys.items():
            g = gen.get(k)
            if g and (g.state != state or g.zh != zh
                      or g.enum_values != enum or g.required != required
                      or _ui_kind(g) != ui
                      or (tuple(g.value_source) if g.value_source else None)
                      != (tuple(vs) if vs else None)):
                diffs.append(
                    f"| {k} | 手建 state={state} required={required} "
                    f"ui={ui} zh={zh!r} enum={enum!r} vs={vs!r} "
                    f"| 生成 state={g.state} required={g.required} "
                    f"ui={_ui_kind(g)} zh={g.zh!r} "
                    f"enum={g.enum_values!r} vs={g.value_source!r} |")
        if missing or extra or diffs:
            lines += [f"## {ep_id}", ""]
            if missing:
                m_fe = [k for k in missing if k in fe_keys]
                m_be = [k for k in missing if k not in fe_keys and k in be_keys]
                m_cap = [k for k in missing
                         if k not in fe_keys and k not in be_keys]
                lines.append(f"- missing({len(missing)}):")
                if m_fe:
                    lines.append(f"  - [FE]({len(m_fe)}): {', '.join(m_fe)}")
                if m_be:
                    lines.append(f"  - [BE]({len(m_be)}): {', '.join(m_be)}")
                if m_cap:
                    lines.append(f"  - [capture]({len(m_cap)}): "
                                 f"{', '.join(m_cap)}")
            if extra:
                lines.append(f"- extra({len(extra)}): {', '.join(extra)}")
            if diffs:
                lines += ["| 键 | 手建 | 生成 |", "|---|---|---|"] + diffs
            lines.append("")
    return "\n".join(lines)
