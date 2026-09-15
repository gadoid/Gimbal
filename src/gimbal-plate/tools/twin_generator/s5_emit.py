"""S5:装订 —— EndpointSpec Python 源码渲染 + 碰撞跳过(手建优先)+ 对照报告。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .ir import ActionIR, FieldIR

_HEADER = '''"""{id} —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: {baseline} | 生成时间: {now}
needs_capture(首跑经 gimbal 执行回填): {nc}
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
    """S4 白名单判据在装订侧复述:read → form,其余按 S4 赋值(carry)。

    对已跑 S4 的字段幂等;对未跑 S4 的裸 FieldIR 也产出合法 state
    (io_spec state 词表 form/collapse/carry)。
    """
    return "form" if f.read else f.state


def _entry_lines(fields: list[FieldIR]) -> str:
    lines = []
    for f in fields:
        kwargs = [f"name={f.key!r}", f"path=f'$.{f.key}'",
                  f"type={f.type_!r}", f"state={_render_state(f)!r}"]
        if f.required:
            kwargs.append("required=True")
        # enum 一致性(io_spec 构造期):default 须 ∈ enum,冲突则弃 default 保 enum
        if f.default is not None and (not f.enum_values or f.default in f.enum_values):
            kwargs.append(f"default={f.default!r}")
        if f.zh:
            kwargs.append(f"description={f.zh!r}")
        if f.enum_values:
            # §3.3③ enum × value_source 互斥:enum 优先(S4 同判),value_source 弃挂
            kwargs.append(f"enum={f.enum_values!r}")
        elif f.value_source:
            kwargs.append(
                f"value_source=ValueSource(view={f.value_source[0]!r}, "
                f"column={f.value_source[1]!r})")
        line = f"            DeclarationEntry({', '.join(kwargs)}),"
        if f.flags:
            line += "  # " + ", ".join(f.flags)
        lines.append(line)
    return "\n".join(lines) or "            # (无字段 — 键面为空)"


def render_endpoint(act: ActionIR, fields: list[FieldIR], baseline: str) -> str:
    nc = [f.key for f in fields if f.flags] or ["(无)"]
    zh = next((f.zh for f in fields if f.key == "action" and f.zh),
              f"{act.controller}.{act.action}")
    head = _HEADER.format(id=act.id, baseline=baseline,
                          now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          nc=", ".join(nc))
    body = _TEMPLATE.format(
        const=act.const_name, id=act.id, zh=zh, baseline=baseline,
        method=act.method, path=act.path, entries=_entry_lines(fields))
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


def compare_faces(all_fields: dict, handbuilt: dict) -> str:
    """三分类差异报告:missing(生成漏)/extra(生成多)/diff(同键字段异)。"""
    lines = ["# 对照报告(生成 vs 手建 ground truth)", ""]
    for ep_id, hb_keys in sorted(handbuilt.items()):
        gen = {f.key: f for f in all_fields.get(ep_id, [])}
        missing = [k for k in hb_keys if k not in gen]
        extra = [k for k in gen if k not in hb_keys]
        diffs = []
        for k, (state, zh, enum, required, vs) in hb_keys.items():
            g = gen.get(k)
            if g and (g.state != state or g.zh != zh
                      or g.enum_values != enum or g.required != required
                      or (tuple(g.value_source) if g.value_source else None)
                      != (tuple(vs) if vs else None)):
                diffs.append(
                    f"| {k} | 手建 state={state} required={required} zh={zh!r} "
                    f"enum={enum!r} vs={vs!r} "
                    f"| 生成 state={g.state} required={g.required} zh={g.zh!r} "
                    f"enum={g.enum_values!r} vs={g.value_source!r} |")
        if missing or extra or diffs:
            lines += [f"## {ep_id}", ""]
            if missing:
                lines.append(f"- missing({len(missing)}): {', '.join(missing)}")
            if extra:
                lines.append(f"- extra({len(extra)}): {', '.join(extra)}")
            if diffs:
                lines += ["| 键 | 手建 | 生成 |", "|---|---|---|"] + diffs
            lines.append("")
    return "\n".join(lines)
