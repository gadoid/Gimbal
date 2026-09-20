"""S2c:前端面提取 —— webpack chunk 的 url/method/表单组/label/payload 字面量。

实探结论(2026-09-20,D:\\fin-test\\static\\js,95 个非 gz chunk):
- 属性名不被 minify:url/method/键名/中文名/控件类型原样存活;
- 业务 POST 的 payload 是动态变量(data:e)——字面量 payload 只覆盖
  GET/查询类;请求面的主力来源是表单配置(1547 条 {type,name,key})
  与 label(4083 条 {label,width,name});
- API 函数块跨 chunk 重复打包(每个页面 chunk 都含 ~360 条 URL),
  URL 命中不能作为表单归属依据;
- 存在巨型共享 bundle(chunk-5e07767f:884 表单 + 507 URL),内含 73 个
  独立表单组 —— 表单必须先按字节间隙分段,再组级归属,否则一锅端。

归属判据(组级):
  chunk 内表单配置按 800 字符间隙切段为"表单组";
  候选 endpoint 由**键倒排索引**定(组内任一键 ∈ 后端键集)——URL 不能作
  候选依据(共享 API 函数块让每个 chunk 都"含有"全部 URL 定义);
  组键集 ∩ 后端键集 ≥ FE_ASSIGN_MIN 且 ≥ 15% 组键数
  且 ≥ 60% 该组在全部候选中的最高交集(近并列如 add/edit 都收)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .ir import ActionIR

FE_ASSIGN_MIN = 3          # 组键与后端键集的最小交集
_GROUP_GAP = 800           # 表单配置切段间隙(字节)
_WINDOW_METHOD = 120       # url:"..." 之后找 method:"..." 的窗口
_WINDOW_PAYLOAD = 300      # url:"..." 之后找 data/params:{...} 的窗口
_MIN_COVER = 0.15          # 交集 / 组键数 下限(表单键常远多于后端规则键)
# 交集 / 最高交集 下限。实测 order 表单模型在家族内呈双集团分布:
# add/book/edit 真并列(44-48/68,共享同一表单)vs page/export 仅 26(55%)
# —— 0.80 恰好切在两集团之间(0.54 与 0.92),既保留真并列又挡住弱命中。
_REL_SCORE = 0.80

# 前端控件类型 → ui_kind 词表(text/number/boolean/select/textarea/json/file/binary/unknown)
FE_TYPE_MAP = {
    "text": "text", "textarea": "textarea", "input": "text",
    "number": "number", "digit": "number",
    "select": "select", "multiple": "select", "radio": "select",
    "checkbox": "select", "switch": "boolean",
    "upload": "file", "file": "file",
    "date": "text", "datetime": "text", "time": "text", "daterange": "text",
}

# 表单初始态模型(data() 无 zh 键)是编辑弹窗的初始值 —— 只归写动作
# 端点;搜索/分页端点吃模型是 extra 主源(T4.4 实测 page 端点 ~150 extra)
_FORM_ACTS = ("add", "edit", "book", "dispatch")


def _is_form_action(action: str) -> bool:
    a = action.lower()
    return any(f in a for f in _FORM_ACTS)

_RE_URL = re.compile(r'url:"([^"]+)"')
_RE_FORM_A = re.compile(          # type ... name ... key(任序两变体)
    r'\{type:"(\w+)"[^{}]*?name:"([^"]+)"[^{}]*?key:"(\w+)"[^{}]*?\}')
_RE_FORM_B = re.compile(
    r'\{type:"(\w+)"[^{}]*?key:"(\w+)"[^{}]*?name:"([^"]+)"[^{}]*?\}')
_RE_LABEL = re.compile(r'\{label:"([^"]+)",width:\d+,name:"(\w+)"')
_RE_PROP = re.compile(       # 表格列(name 变体;width 可选)
    r'\{label:"([^"]+)"(?:,width:\d+)?,prop:"(\w+)"')
_RE_DATA = re.compile(r'(?:data|params):\{([^{}]{3,}?)\}')
_RE_KEY = re.compile(r'([A-Za-z_]\w*)\s*:')
# 表单初始态键值对:key:""/null/[]/{}/短字面量(Vue data() 的 add/edit 表单模型)
_RE_KV = re.compile(
    r'([A-Za-z_]\w*):(?:"(?:[^"]{0,40})"|null|\[\]|\{\}|\d+(?:\.\d+)?)')

_FORM_MODEL_MIN = 15        # 表单模型最少唯一键数
_FORM_MODEL_EMPTY = 0.60    # 值为空串/null/[] 的占比下限(防菜单等配置对象)


@dataclass
class FeFace:
    """单 endpoint 的前端面(表单/label/payload 三层,置信度递减)。"""
    path: str
    method: str = ""                       # FE 实证 method(小写;空=未命中)
    chunks: list[str] = field(default_factory=list)
    form_keys: dict[str, dict] = field(default_factory=dict)   # key → {zh, fe_type}
    label_keys: dict[str, str] = field(default_factory=dict)   # key → zh(中置信)
    payload_keys: dict[str, str] = field(default_factory=dict) # key → example 值(可空)


def _fe_path(path: str) -> str:
    """BE 路径 /api/order/orderEntrust/orderAdd → FE /order/orderEntrust/orderAdd。"""
    return path[4:] if path.startswith("/api/") else path


def _scan_chunk(f: Path) -> dict:
    s = f.read_text(encoding="utf-8", errors="replace")
    urls: set[str] = set()
    methods: dict[str, str] = {}
    payload: dict[str, dict[str, str]] = {}   # url → {key: value}
    for m in _RE_URL.finditer(s):
        u = m.group(1)
        urls.add(u)
        mm = re.search(r"method:\"(\w+)\"",
                       s[m.end():m.end() + _WINDOW_METHOD])
        if mm:
            methods.setdefault(u, mm.group(1).lower())
        for dm in _RE_DATA.finditer(s[m.end():m.end() + _WINDOW_PAYLOAD]):
            for km in _RE_KEY.finditer(dm.group(1)):
                payload.setdefault(u, {}).setdefault(km.group(1), "")
    spans = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3))
             for m in _RE_FORM_A.finditer(s)]
    spans += [(m.start(), m.end(), m.group(1), m.group(3), m.group(2))
              for m in _RE_FORM_B.finditer(s)]
    spans.sort()
    groups: list[list[tuple[str, str, str]]] = []
    last_end = -1
    for start, end, fe_type, zh, key in spans:
        if groups and start - last_end <= _GROUP_GAP:
            groups[-1].append((fe_type, zh, key))
        else:
            groups.append([(fe_type, zh, key)])
        last_end = end
    # findall 返回 (zh, key) 元组 —— 必须倒手,直接 dict() 会把中文当键
    labels = {k: zh for zh, k in _RE_LABEL.findall(s)}
    labels.update({k: zh for zh, k in _RE_PROP.findall(s)})
    # 表单初始态模型:KV 连缀串(key:""/null/... 相邻成段)≥15 唯一键且
    # ≥60% 空值 → add/edit 表单的完整字段面(无 zh,zh 走 Lang/header/column 链)
    models: list[list[tuple[str, str, str]]] = []
    run: list = []            # [(start,end,key,is_empty)]
    for m in _RE_KV.finditer(s):
        if run and m.start() - run[-1][1] > 3:
            _flush_model(run, models)
            run = []
        val = m.group(0)[m.group(0).index(":") + 1:]
        run.append((m.start(), m.end(), m.group(1), val in ('""', "null", "[]", "{}")))
    _flush_model(run, models)
    return {"name": f.name, "urls": urls, "methods": methods,
            "payload": payload, "groups": groups, "models": models,
            "labels": labels}


def _flush_model(run: list, models: list) -> None:
    """把 KV 连缀串收口为表单模型组(过门槛才收)。"""
    if len(run) < _FORM_MODEL_MIN:
        return
    keys = [k for *_s, _e, k, _v in run]
    uniq = set(keys)
    if len(uniq) < _FORM_MODEL_MIN:
        return
    empty = sum(1 for *_s, _e, _k, v in run if v)
    if empty / len(run) < _FORM_MODEL_EMPTY:
        return
    models.append([( "", "", k) for k in keys])


def scan_frontend(js_dir: Path, actions: list[ActionIR]) -> dict[str, FeFace]:
    """扫全部非 gz chunk;返回 act.id → FeFace,并把 FE method 回写 act.method。"""
    chunks = [_scan_chunk(f) for f in sorted(js_dir.glob("*.js"))]

    be_keys = {id(a): {r.key for r in a.rules} | set(a.reads) for a in actions}
    # 键倒排索引:候选 endpoint 由组内键定(URL 定义全局重复,不能作依据)
    key_owners: dict[str, list[ActionIR]] = {}
    for a in actions:
        for k in be_keys[id(a)]:
            key_owners.setdefault(k, []).append(a)

    faces: dict[str, FeFace] = {}
    # 1) 组级归属:每 chunk 的表单组(搜索/编辑段)+ 表单初始态模型,
    #    倒排索引定候选后打分
    for c in chunks:
        owned_groups: list[tuple[list[ActionIR], list]] = []
        for is_model, grp in ([(False, g) for g in c["groups"]]
                              + [(True, m) for m in c["models"]]):
            gk = {k for *_t, _z, k in grp}
            cand: dict[int, ActionIR] = {}
            for k in gk:
                for a in key_owners.get(k, []):
                    # 模型组(编辑弹窗初始态)只归写动作端点
                    if is_model and not _is_form_action(a.action):
                        continue
                    cand[id(a)] = a
            scores: list[tuple[int, ActionIR]] = []
            for aid, a in cand.items():
                inter = len(gk & be_keys[aid])
                if inter >= FE_ASSIGN_MIN and inter >= _MIN_COVER * len(gk):
                    scores.append((inter, a))
            if not scores:
                continue
            mx = max(i for i, _a in scores)
            winners = [a for i, a in scores if i >= _REL_SCORE * mx]
            owned_groups.append((winners, grp))
        # 拥有 ≥1 组的 endpoint 才吃该 chunk 的 label(表格列,中置信)
        for ws, grp in owned_groups:
            for a in ws:
                face = faces.setdefault(a.id, FeFace(path=a.path))
                for fe_type, zh, key in grp:
                    face.form_keys.setdefault(key, {"zh": zh, "fe_type": fe_type})
        owners = {a.id for ws, _g in owned_groups for a in ws}
        for aid in owners:
            for key, zh in c["labels"].items():
                faces[aid].label_keys.setdefault(key, zh)
    # 2) URL 精确命中 → method / payload
    for act in actions:
        fe_p = _fe_path(act.path)
        hit = [c for c in chunks if fe_p in c["urls"]]
        if not hit:
            continue
        face = faces.setdefault(act.id, FeFace(path=act.path))
        m = next((c["methods"][fe_p] for c in hit if fe_p in c["methods"]), "")
        if m:
            face.method = m
            act.method = m.upper()          # T2.2:FE 是 method 真源
            act.method_assumed = False
        face.chunks = sorted({c["name"] for c in hit} | set(face.chunks))
        for c in hit:
            for k, v in c["payload"].get(fe_p, {}).items():
                face.payload_keys.setdefault(k, v)
    return {k: v for k, v in faces.items()
            if v.method or v.form_keys or v.payload_keys or v.label_keys}


def fe_to_json(faces: dict[str, FeFace]) -> dict:
    return {k: {
        "path": v.path, "method": v.method, "chunks": v.chunks,
        "form_keys": v.form_keys, "label_keys": v.label_keys,
        "payload_keys": v.payload_keys,
    } for k, v in faces.items()}
