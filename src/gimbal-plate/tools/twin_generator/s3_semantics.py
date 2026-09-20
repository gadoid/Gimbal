"""S3:语义富化 —— zh 合并(rule>column>derived)/type 映射/默认值/enum(rule)。

Enum 类抽取仅作报告候选(v1 不自动挂 enum,scope 控制);字段集 =
活跃规则键 ∪ 被注释规则键 ∪ 读取键。

节点形状 probe 实录(task-6,fixture OrderEnum):
declaration_list 子序 = [const_declaration, comment, ...] 相邻命名兄弟,
中间无匿名节点(不同于 property 数组里的 ','),children[i+1] 直接命中
同行行尾 comment;const_element 是 const_declaration 直接子节点
(const/; 为匿名),其子 = name + '='(匿名)+ integer|string。
"""
from __future__ import annotations

import re
from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes, is_string_literal
from .ir import ActionIR, FieldIR, RuleEntry, snake
from .schema_source import ColumnCatalog, ColumnInfo

_INT_TYPES = ("int", "bigint", "tinyint", "smallint", "mediumint")
_NUM_TYPES = ("decimal", "float", "double")


def load_enums(app_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Common/Enum/*.class.php:类名 → [(值, 中文)]。

    两源合并:$list(self::CONST => '中文' 直接映射,优先)
    + const 行尾注释(zh 兜底)。
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for f in sorted((app_root / "Common" / "Enum").glob("*.class.php")):
        pf = load(f)
        for n, _c, decl in classes(pf):
            entries: list[tuple[str, str]] = []
            const_vals: dict[str, str] = {}
            children = list(decl.children)
            for i, node in enumerate(children):
                if node.type == "const_declaration":
                    for el in node.children:
                        if el.type != "const_element":
                            continue
                        name = next((c for c in el.children if c.type == "name"),
                                    None)
                        val_n = next((c for c in el.children
                                      if c.type == "integer"
                                      or is_string_literal(c)), None)
                        if name is None or val_n is None:
                            continue
                        const_vals[text_of(pf, name)] = \
                            text_of(pf, val_n).strip("'\"")
                        nxt = children[i + 1] if i + 1 < len(children) else None
                        zh = ""
                        if nxt is not None and nxt.type == "comment" \
                                and nxt.start_point[0] == node.start_point[0]:
                            zh = text_of(pf, nxt).lstrip("/ ").strip()
                        entries.append((const_vals[text_of(pf, name)], zh))
                elif node.type == "property_declaration":
                    # public static $list = [ self::NAME => 'zh', 1 => 'zh' ]
                    body = text_of(pf, node)
                    lm = re.search(r"\$list\s*=\s*\[(.*?)\]", body, re.S)
                    if not lm:
                        continue
                    for cm in re.finditer(
                            r"(?:(?:self|static)::(\w+)|(\d+))\s*=>"
                            r"\s*['\"]([^'\"]+)['\"]", lm.group(1)):
                        name, lit, zh = cm.group(1), cm.group(2), cm.group(3)
                        val = const_vals.get(name, "") if name else lit
                        if val != "":
                            entries.append((val, zh))
            if entries:
                out.setdefault(n, []).extend(entries)
    return out


def _type_of(col_type: str) -> str:
    base = col_type.split("(")[0].lower()
    if base in _INT_TYPES:
        return "integer"
    if base in _NUM_TYPES:
        return "number"
    return "string"


def _rule_index(rules: list[RuleEntry]) -> dict[str, RuleEntry]:
    out: dict[str, RuleEntry] = {}
    for r in rules:                     # 活跃行优先(后写覆盖时保活跃)
        if r.active:
            out[r.key] = r
    for r in rules:
        out.setdefault(r.key, r)
    return out


def _zh_of(key: str, ridx: dict[str, RuleEntry],
           lang: dict[str, str], fe) -> str:
    """键的 zh 原始源查询(规则 > lang > fe 表单配置)。"""
    r = ridx.get(key)
    if r and r.zh:
        return r.zh
    if key in lang:
        return lang[key]
    if fe:
        fk = fe.form_keys.get(key)
        if fk and fk.get("zh"):
            return fk["zh"]
    return ""


def _pick_column(cols: list, mod_tables: set[str]) -> tuple[ColumnInfo, bool]:
    """T3.3 上下文选表:模块表过滤→唯一用之→注释非空优先。

    → (选中列, 是否平局)。零模块命中回退全局首现(平局=False)。
    """
    in_mod = [c for c in cols
              if any(c.table == t or c.table.startswith(t + "_")
                     for t in mod_tables)]
    if not in_mod:
        return cols[0], False
    with_zh = [c for c in in_mod if c.comment]
    pool = with_zh or in_mod
    if len(pool) == 1:
        return pool[0], False
    # 多候选且注释不一致 → 平局(上游 flag zh_ambiguous)
    zhs = {c.comment for c in pool}
    return pool[0], len(zhs) > 1


_ENUM_SUFFIXES = ("_type", "_status", "_state")

# T4.1:表单写操作(check|submit 双态大表单)—— 手建 ground truth
# 实证 required 全 False(暂存分支字段可空,必填语义归场景层),
# require 直译在这些动作下降级。
_FORM_ACTIONS = ("add", "edit", "book", "dispatch")


def _is_form_action(action: str) -> bool:
    a = action.lower()
    return any(f in a for f in _FORM_ACTIONS)


def _required_of(rule: RuleEntry | None, read: bool, key: str,
                 action: str, has_action_key: bool) -> bool:
    """T4.1 required 分支(替代 require|present 直译)。

    1. 活跃 require 且非表单动作 → True;
    2. 活跃 require 且表单动作(check|submit 双态)→ False(降级,
       手建实证 required 全空);
    3. 仅 present → False(present 语义是"键须存在"归 must_include;
       手建实证 present 键 required 全 False);
    4. 无规则但键∈{page_no,page_size,sort_field,sort_order} 且动作含
       page/list → True(手建实证列表端点四键全必填)。
    """
    if rule and rule.active:
        if rule.hard_required():
            return not (has_action_key and _is_form_action(action))
        return False                        # present / 其余 → 非必填
    if key in ("page_no", "page_size", "sort_field", "sort_order") and \
            ("page" in action.lower() or "list" in action.lower()):
        return True
    return False

# fin SUT 通用动作键:手建 5 端点全部 check|submit(领域约定,内置)
ACTION_ENUM = ["check", "submit"]

# fin SUT 通用分页/排序键:手建 3 个 page 端点全部实证(page_no/page_size/
# sort_field/sort_order 的 zh 与 sort_order 的 asc/desc 闭集),领域约定内置
PAGE_KEY_ZH = {"page_no": "页码", "page_size": "每页条数",
               "sort_field": "排序字段", "sort_order": "排序方向"}
SORT_ORDER_ENUM = ["asc", "desc"]


def _match_enum_class(key: str, enums: dict, module: str = "") -> str | None:
    """T3.2 挂载判据一:键名 → Enum 类。

    revoke_status → 剥 _status → revoke;类名去 Enum 后小写
    (orderrevokestatus)须以 base 结尾 —— 防止短 base 误吸
    (如 status 剥完为空,不挂)。类 stem 还须包含模块名
    (order 模块的 account_status 不配 AccountEnum 泛类)。
    """
    base = ""
    key_suf = ""
    for suf in _ENUM_SUFFIXES:
        if key.endswith(suf) and len(key) > len(suf):
            base, key_suf = key[:-len(suf)], suf[1:]   # 去下划线
            break
    if not base:
        return None
    mod = module.lower()
    for cls in enums:
        stem = cls[:-4].lower() if cls.endswith("Enum") else cls.lower()
        if mod and mod not in stem:
            continue        # 泛类(AccountEnum)不跨模块挂
        # 类名常自带 Status/Type 尾(无下划线形式;键剥了,类名也剥再比)
        cls_suf = ""
        for suf in ("status", "type", "state"):
            if stem.endswith(suf) and len(stem) > len(suf):
                stem, cls_suf = stem[:-len(suf)], suf
                break
        # 后缀族一致才收:pay_type(方式)不配 PayStatusEnum(状态);
        # 类名无后缀(OrderEnum)对任何键后缀开放。
        if cls_suf and cls_suf != key_suf:
            continue
        if stem.endswith(base):
            return cls
    return None


def _enum_map(entries: list[tuple[str, str]]) -> dict[str, str]:
    """[(值, zh)] → 有序去重($list 后写覆盖 const 空注释)。"""
    out: dict[str, str] = {}
    for v, zh in entries:
        out.setdefault(v, "")
        if zh:
            out[v] = zh
    return out


def _main_table(catalog: ColumnCatalog, act: ActionIR) -> str | None:
    """form 动作主表:控制器同名表优先,退模块表
    (sys_order_entrust 不存在 → sys_order;order_add 实证该族 save-all)。"""
    for cand in (f"sys_{snake(act.controller)}", f"sys_{act.module.lower()}"):
        if cand in catalog.by_table:
            return cand
    return None


def enrich(actions: list[ActionIR], catalog: ColumnCatalog,
           fe_faces: dict | None = None,
           lang_views: dict[str, dict[str, str]] | None = None,
           header_views: dict[str, dict[str, str]] | None = None,
           mod_tables_views: dict[str, set[str]] | None = None,
           enums: dict[str, list[tuple[str, str]]] | None = None,
           groups: dict[str, list[tuple[str, list[RuleEntry]]]] | None = None,
           container_sigs: dict[str, list[str]] | None = None,
           ) -> dict[str, list[FieldIR]]:
    """lang_views:act.id → {key: zh};header_views:控制器小写 → {key: zh};
    mod_tables_views:模块 → 表前缀集合(module_tables,跨表 zh 选表);
    groups:act.id → [(容器键, 行规则)](T5.3 s2_groups 检测);
    container_sigs:act.id → [容器键](getDataArray 信号,无行规则)。"""
    all_fields: dict[str, list[FieldIR]] = {}
    fe_faces = fe_faces or {}
    lang_views = lang_views or {}
    header_views = header_views or {}
    mod_tables_views = mod_tables_views or {}
    enums = enums or {}
    groups = groups or {}
    container_sigs = container_sigs or {}
    for act in actions:
        ridx = _rule_index(act.rules)
        fe = fe_faces.get(act.id)
        lang = lang_views.get(act.id, {})
        header = header_views.get(act.controller.lower(), {})
        mtables = mod_tables_views.get(act.module, set())
        # FE 高置信键(form/payload)入集 —— 补后端未见键(missing 主因)
        fe_high: dict[str, dict] = {}
        if fe:
            fe_high = {**fe.payload_keys, **{k: {} for k in fe.form_keys}}
        keys: list[str] = []
        for k in list(ridx) + list(fe_high):
            if k not in keys:
                keys.append(k)
        # T4.4 extra 收紧:service-origin 读取键仅 FE 佐证才入集;
        # request-origin(控制器/Validator/持请求直调)无门槛。
        for k, r in act.reads.items():
            if k in keys:
                continue
            if r.origin == "request" or k in fe_high:
                keys.append(k)
        # T4.1 分支 4 配套:分页动作补 page_no/page_size/sort_*(手建实证必有)
        act_l = act.action.lower()
        if "page" in act_l or "list" in act_l:
            for k in ("page_no", "page_size", "sort_field", "sort_order"):
                if k not in keys:
                    keys.append(k)
        fields: list[FieldIR] = []
        has_action_key = "action" in keys
        for key in keys:
            rule = ridx.get(key)
            read = act.reads.get(key)
            cols = catalog.by_name.get(key, [])
            col, zh_ambiguous = (_pick_column(cols, mtables)
                                 if cols else (None, False))
            f = FieldIR(
                key=key,
                read=read is not None,
                # T4.1 四分支:require 直译只对非表单动作成立
                required=_required_of(rule, read is not None, key,
                                      act.action, has_action_key),
                # 校验派生只认活跃行;被注释行仅贡献 zh(保留注释行的目的)
                must_include=bool(rule and rule.active
                                  and (rule.required() or rule.must_include())),
                zh=rule.zh if rule and rule.zh else "",
                zh_source="rule" if rule and rule.zh else "",
                enum_values=rule.enum_values() if rule and rule.active else None,
                default=read.default if read and read.default is not None else None,
                col_comment=col.comment if col else "",
                col_type=col.col_type if col else "",
                tables=[c.table for c in cols],
            )
            if zh_ambiguous:
                f.flags.append("zh_ambiguous")
            # T3.2:Enum 类挂载 —— 键名匹配且规则未给 in: 才挂(保守);
            # 规则 in: 与类值集冲突时规则赢,留 enum_candidate 注释。
            if enums:
                cls = _match_enum_class(key, enums, act.module)
                if cls:
                    vals = list(_enum_map(enums[cls]))
                    rule_in = (rule.enum_values()
                               if rule and rule.active else None)
                    if rule_in is not None and set(map(str, rule_in)) != set(vals):
                        f.enum_candidate = cls       # 冲突:规则赢
                    elif f.enum_values is None:
                        f.enum_values = vals
                        f.enum_candidate = cls
            # 通用动作键:fin 领域约定 check|submit(手建 5 端点实证)
            if f.enum_values is None and key == "action":
                f.enum_values = list(ACTION_ENUM)
            # 通用排序键:asc/desc 闭集(手建 3 个 page 端点全实证)
            if f.enum_values is None and key == "sort_order":
                f.enum_values = list(SORT_ORDER_ENUM)
            # S2c 前端面:form 高置信(zh+fe_type);payload 键(example)
            if fe:
                fk = fe.form_keys.get(key)
                if fk:
                    f.fe_zh = fk.get("zh", "")
                    f.fe_type = fk.get("fe_type", "")
                    f.fe_confidence = "high"
                if key in fe.payload_keys:
                    f.fe_confidence = "high"
                    f.example = fe.payload_keys.get(key) or ""
                elif key in fe.label_keys and not f.fe_confidence:
                    f.fe_confidence = "medium"
                    if not fe.form_keys.get(key):
                        f.fe_zh = fe.label_keys.get(key, "")
            # zh 链:rule > lang > fe_form(high) > column(上下文选表 T3.3)
            # > fe_label(medium) > derived
            # (export_header 档 T3.4 插到 column 之前)
            if not f.zh and key in lang:
                f.zh, f.zh_source = lang[key], "lang"
            if not f.zh and f.fe_confidence == "high" and f.fe_zh:
                f.zh, f.zh_source = f.fe_zh, "frontend"
            if not f.zh and key in header:
                f.zh, f.zh_source = header[key], "header"
            if not f.zh and col and col.comment:
                f.zh, f.zh_source = col.comment, "column"
            if not f.zh and f.fe_confidence == "medium" and f.fe_zh:
                f.zh, f.zh_source = f.fe_zh, "frontend_label"
            if not f.zh and key.endswith("_name"):
                base_key = key[:-5]           # customer_name → customer
                base_zh = ""
                for cand in (base_key, base_key + "_id"):
                    base_zh = _zh_of(cand, ridx, lang, fe)
                    if base_zh:
                        break
                if base_zh:
                    f.zh, f.zh_source = base_zh + "名称", "derived"
            # 日期区间键:etd_start → 基键 zh + 开始/结束(搜索表单约定)
            if not f.zh and key.endswith(("_start", "_end")):
                base_zh = _zh_of(key.rsplit("_", 1)[0], ridx, lang, fe)
                if base_zh:
                    f.zh = base_zh + ("开始" if key.endswith("_start") else "结束")
                    f.zh_source = "derived"
            # 复数 id 列表:order_ids → 订单ID + 列表
            if not f.zh and key.endswith("_ids"):
                base_zh = _zh_of(key[:-1], ridx, lang, fe)
                if base_zh:
                    f.zh, f.zh_source = base_zh + "列表", "derived"
            # 分页/排序键 zh:领域约定内置(手建 3 个 page 端点全实证)
            if not f.zh and key in PAGE_KEY_ZH:
                f.zh, f.zh_source = PAGE_KEY_ZH[key], "builtin"
            f.type_ = _type_of(f.col_type) if f.col_type else "string"
            if f.default is None and col and col.default:
                f.default = col.default
            fields.append(f)
        # 主表列并入(form 动作;order_add 实证 PHP save-all:sys_order 193/193
        # 列全在手建面 —— 生成器键集 = 规则∪读取∪FE 不含表列,此处静态补齐;
        # 未读列 state 自然落 carry,与手建 13 form/227 carry 分布同构)
        if _is_form_action(act.action):
            mt = _main_table(catalog, act)
            if mt:
                have = {f.key for f in fields}
                for col in catalog.by_table[mt]:
                    if col.column in have:
                        continue
                    fields.append(FieldIR(
                        key=col.column,
                        zh=col.comment, zh_source="column" if col.comment else "",
                        col_comment=col.comment, col_type=col.col_type,
                        tables=[mt], type_=_type_of(col.col_type),
                    ))
        # T5.3 行容器:foreach + paramVerification 分组 —— 容器键标 array,
        # 行规则建子 FieldIR(zh 链同款:rule > lang > header > column > derived)
        for container, grules in groups.get(act.id, []):
            f = next((x for x in fields if x.key == container), None)
            if f is None:
                f = FieldIR(key=container, read=True)   # foreach 即读取
                fields.append(f)
            f.container = True
            f.type_ = "array"
            gidx = _rule_index(grules)
            for key in gidx:
                rule = gidx.get(key)
                cols = catalog.by_name.get(key, [])
                col, zh_ambiguous = (_pick_column(cols, mtables)
                                     if cols else (None, False))
                c = FieldIR(
                    key=key, read=True,
                    required=_required_of(rule, True, key,
                                          act.action, has_action_key),
                    must_include=bool(rule and rule.active
                                      and rule.must_include()),
                    zh=rule.zh if rule and rule.zh else "",
                    zh_source="rule" if rule and rule.zh else "",
                    enum_values=rule.enum_values() if rule and rule.active else None,
                    col_comment=col.comment if col else "",
                    col_type=col.col_type if col else "",
                    tables=[x.table for x in cols],
                )
                if zh_ambiguous:
                    c.flags.append("zh_ambiguous")
                if enums and c.enum_values is None:
                    cls = _match_enum_class(key, enums, act.module)
                    if cls:
                        c.enum_values = list(_enum_map(enums[cls]))
                        c.enum_candidate = cls
                if not c.zh and key in lang:
                    c.zh, c.zh_source = lang[key], "lang"
                if not c.zh and key in header:
                    c.zh, c.zh_source = header[key], "header"
                if not c.zh and col and col.comment:
                    c.zh, c.zh_source = col.comment, "column"
                if not c.zh and key.endswith("_name"):
                    base_key = key[:-5]
                    base_zh = ""
                    for cand in (base_key, base_key + "_id"):
                        base_zh = _zh_of(cand, gidx, lang, fe)
                        if base_zh:
                            break
                    if base_zh:
                        c.zh, c.zh_source = base_zh + "名称", "derived"
                c.type_ = _type_of(c.col_type) if c.col_type else "string"
                f.children.append(c)
        # getDataArray 容器信号(order 族):无行规则,children 按容器表
        # sys_<module>_<key> 解析;规则组已标的容器跳过(rule 证据优先)
        for ckey in container_sigs.get(act.id, []):
            f = next((x for x in fields if x.key == ckey), None)
            if f is None:
                f = FieldIR(key=ckey, read=True)   # getDataArray 即读取
                fields.append(f)
            if f.container:
                continue
            f.container = True
            f.type_ = "array"
            tbl = f"sys_{act.module.lower()}_{ckey}"
            cols = catalog.by_table.get(tbl, [])
            if cols:
                for col in cols:
                    f.children.append(FieldIR(
                        key=col.column, read=True,
                        zh=col.comment, zh_source="column" if col.comment else "",
                        col_comment=col.comment, col_type=col.col_type,
                        tables=[tbl], type_=_type_of(col.col_type)))
            else:
                f.flags.append("needs_capture:children")
        all_fields[act.id] = fields
    return all_fields
