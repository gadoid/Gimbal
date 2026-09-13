"""注入条目物化(spec v3 §3)— 平台层 patch,引擎/plate 零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(steps[si].strategy
追加 Assign 直补 + asserts patch),materialize_run_copy 其后照旧。
值注入与数据集 vars 注入完全解耦(正交叠加):compose 不触碰 config.vars。
"""
import copy
import re
from typing import Any, Callable

from loguru import logger

from .jsonpath import JsonPathError, NodeKind, _parse, exists


def _is_context_readable(source: Any) -> bool:
    """引擎会把这两类字符串当**引用**解析,而不是字面量
    (gimbal/strategy/builtin/utils.py:63-106 `_resolve_source_value`):
    * ``"$.*"`` — scope 落到 STEP/SCENARIO(Assign 默认 SCENARIO)时按
      JSONPath 从场景上下文读(jsonpath 查不到 → None);**兜底只对这类有效**
      (它穿过预处理,见 `_assign_strategy`);
    * 整串 ``"${...}"`` — 按变量名从上下文读(读不到 → None);这类在
      **预处理阶段**就被展开,平台侧兜不住(见 `_assign_strategy`)。
    其余字符串与全部非字符串(含 dict/list)一律原样直通。"""
    if not isinstance(source, str):
        return False
    if source.startswith("$."):
        return True
    return source.startswith("${") and source.endswith("}")


def _assign_strategy(value: Any, target: str) -> dict[str, Any]:
    """偏离值 → Assign 策略 dict(spec v3 §3:引擎/plate 零改动)。

    用户 value 的语义是「原样覆写不 coerce」,但引擎对两类字符串会当
    **引用**处理。`default` + `required: false` 只对 **`"$."` 前缀类**
    是有效兜底:这类串不是模板(预处理器的模板正则只认 `${...}`,
    gimbal/utils/jsonpath.py:603/736)→ 原样穿过预处理 → Assign 执行时
    JSONPath 读不到得 None,而此时 `required` 默认 True 会整步 FAILED
    (assign.py:35-45;BEFORE_REQUEST 失败即不发请求,statemachine/
    states.py:63)。带上 `default`(=字面量)+ `required:false` 后:
    assign.py 先 default 后 required,读不到时写字面量而非失败。
    其余值(含普通字符串 / dict / list / null)不带键,基座字段全取默认。

    **整串 `"${...}"` 类不可兜**(引擎语义所限,记录不兜;不加键也不改
    行为):引擎在**任何策略执行之前**先整体预处理整个 scenario
    (gimbal/core/scenario_runner.py:258-266),`_resolve_strategy` 把
    `Assign.source` 与 `Assign.default` **一并**过 `_resolve_or_fail`
    (gimbal/preprocessor/scenario_preprocessor.py:416-429),于是
      · config.vars 无同名变量 → 预处理阶段直接 `ValueError`
        (…source 模板变量未找到)—— **比 Assign 早**,default 从未被
        读过,失败点也不是 BEFORE_REQUEST;
      · config.vars 有同名变量 → source/default 双双被改写成变量值 →
        写下去的是 vars 值,**字面量不写入**(该偏离对该字段不生效)。
    平台侧唯一的解法是往 config.vars 塞哨兵变量 —— spec §3 把「compose
    不触碰 config.vars」定为核心保证,不做。编辑器对该类显形告警。

    边界二(不可修):JSON null 偏离值无法送达 —— plate 导出
    `model_dump(mode="json", exclude_none=True, ...)`
    (gimbal_plate/export/gimbal.py:279)把 `source: None` 整键丢弃,而
    引擎 `Assign.source: Any` 必填(gimbal/schema/strategy.py)→ 该 case
    加载即 `Scenario.model_validate` 失败。此处不置 `required: false`
    (改不了结局,只把失败点往后挪);编辑器对 null 值显形警告。

    边界三(记录):`$.` 类若上下文里**恰好存在**同名 JSONPath,解析命中
    优先于字面量 —— 该 value 被上下文值覆写。编辑器有可见提示。"""
    st: dict[str, Any] = {"kind": "assign", "source": value, "target": target}
    if _is_context_readable(value):
        st["default"] = value
        st["required"] = False
    return st


_ARRAY_IDX_RE = re.compile(r"\[\d+\]")


def _template_path(jsonpath: str) -> str:
    """实例路径 → 模板形态(剥数组下标:$.items[0].sku → $.items.sku)。
    复用前端 `declarations.toTemplatePath` 的同一规则 —— 契约声明是模板
    路径,条目路径是实例路径,判定必须两形态都试(spec v3.1 §2.1)。"""
    return _ARRAY_IDX_RE.sub("", jsonpath)


def _body_leaf_paths(body: Any) -> list[str]:
    """body 叶子路径(实例形态,数组带 ``[i]``)—— 与前端 ``fieldPathsOf``
    的 body 面同语义:dict/list 递归、数组出 ``[i]``、标量收叶子。

    根缺席(步骤无 ``request.body``)⇒ **无叶子**(前端 ``walk(undefined)``
    早退);嵌套 JSON null 是**显式叶子**(前端同)。键含 ``.`` 时照抄原键
    (路径因此不是可逆的段切分,但这正是两侧一致的形态 —— 前缀子句按
    段边界字面比)。"""
    out: list[str] = []

    def walk(v: Any, path: str) -> None:
        if isinstance(v, dict):
            for k, val in v.items():
                walk(val, f"{path}.{k}" if path else f"$.{k}")
            return
        if isinstance(v, list):
            for i, item in enumerate(v):
                walk(item, f"{path or '$'}[{i}]")
            return
        out.append(path or "$")

    if body is not None:
        walk(body, "")
    return out


def _container_prefixes(path: str) -> list[str]:
    """路径的各级容器前缀(spec §2.1 ``prefixes``):段边界 —— ``.`` 之后 /
    ``[`` 之前。``$.a.b`` → ``['$', '$.a']``;``$.tags[0]`` → ``['$', '$.tags']``。"""
    return [path[:i] for i, ch in enumerate(path) if i and ch in ".["]


def injectable_universe(body: Any, declared: Any) -> set[str]:
    """每步的可注入面(spec v3.1 §2.1 公式;**纯函数**,由调用方按步骤记忆化复用):
    body 叶子 ∪ 其容器前缀 ∪ normalize(declared) ∪ 其前缀 ∪ {"$"}。

    此前这段公式**藏在** :func:`_path_resolvable` 里、每次判定都重建一遍
    (且重建的那份只在函数内可见)。抽成纯函数后:调用方(dispatcher)按步
    预计算一次、判定只查表(spec §2.1 的「判定面不耦合网络 I/O」),并且
    它自己可被单测钉住。

    ``declared`` 侧一律过 :func:`_template_path` 归一 —— 声明面条目自身的
    路径形态是自由的(plate 只强制 children 子树为模板态,顶层条目可带实例
    下标,如 ``$.supplier[0].code``),不归一就会出现「编辑器判活、dispatch
    静默 skip」的判定层分裂(与前端 ``injectablePathSetOf`` 的落点一致)。"""
    universe: set[str] = {"$"}
    for p in _body_leaf_paths(body):
        universe.add(p)
        universe.update(_container_prefixes(p))
    # §5 例外:两侧同为「本步无声明」的缺省形(``None`` / ``frozenset()``),
    # 等价性一眼可判 —— 循环体一次不跑,结果同。``None`` 作为降级标记的含义
    # 属于调用方(dispatcher 的 ``face_by_step``),本函数不区分二者。
    for p in (declared or ()):
        if not isinstance(p, str):
            continue
        t = _template_path(p)
        universe.add(t)
        universe.update(_container_prefixes(t))
    return universe


def _body_target(jsonpath: str) -> str:
    """条目路径 → Assign 的 target:``$.amount`` → ``$.request_body.amount``;
    根 ``"$"`` → ``$.request_body``。

    **判定与物化共用**(Z1)::func:`_path_resolvable` 的宿主判据与
    :func:`compose_injection_scenario` 的物化必须是同一个 target 串 ——
    各拼一份的话,一侧改了前缀另一侧不动,判决与物化就静默分叉。"""
    return "$.request_body" + (jsonpath[1:] if jsonpath != "$" else "")


def _path_resolvable(jsonpath: str, body: Any, universe: set[str]) -> bool:
    """判定(spec v3.1 §2.1):两形态命中 universe 即活;否则退回 body 精确存在性
    (兜底吃 **dict 宿主**,见末段 —— 它比可注入面多认「空容器本身」,方向是
    「少判死」)。

    可注入面(spec §2.1 公式)= :func:`injectable_universe`,由**调用方**预计算
    后传入(此前每次判定就地重建):
    body(si) ∪ prefixes(body(si)) ∪ normalize(declared(si))
    ∪ prefixes(normalize(declared(si))) ∪ {"$"}。

    body 面此前**替代**成了 ``exists(body, jp)``(实例精确判),少了
    ``prefixes(body)`` 与两形态的前缀子句 ⇒ 「编辑器判活、dispatch 静默
    skip」的残余:``body={"tags":["a","b"]}`` + ``$.tags[9]``(前端经
    ``toTemplatePath`` 得 ``$.tags`` 命中前缀,后端越界判死)、
    ``body={"a":{"b.c":1}}`` + ``$.a.b``(键含点,前端前缀命中 ``$.a.b.c``)。

    **前缀子句随 universe 一起预计算**:universe 建时已把每个叶子/声明路径的
    各级容器前缀(`_container_prefixes`)**materialize** 成成员,故原先那段
    「遍历 universe 找 ``form + "."`/``form + "["`` 前缀」的扫描是**死代码**
    —— 命中它的 p 必然意味着 form 是 p 的容器前缀、form 已在 universe 里,
    成员判定先一步就返回了。删掉它不改变任何判定结果(等价性由既有用例与
    ``test_body_face_covers_container_prefixes_like_frontend`` 系列钉住)。

    ``exists`` 兜底**只对 dict 宿主**生效(Z1):兜底前先过 :func:`_host_conflict`
    —— 与写侧**同一判据、同一段走法**,判定与物化不得各写一份。非 dict 宿主上
    ``_eval_nodes`` 的 FIELD 分支走 ``getattr``,于是
    ``exists({'note':'hello'}, '$.note.replace')`` 取到绑定的 ``str.replace``
    方法 ⇒ 判活,而写侧 ``_set_at`` 遇非 dict 即 ``data={}`` ⇒ ``note`` 整体换成
    ``{"replace": v}``(请求体改形)。中间宿主(``$.note`` 之于 ``{'note':'hello'}``)
    与**根** body 本身(``exists("raw", "$.upper")``)都算宿主,两处都挡。
    宿主是 dict 时兜底照旧:它比可注入面多认「空容器本身」
    (``body={"items":[]}`` 的 ``$.items`` 无叶子、无前缀 ⇒ 前端判死而后端
    判活)—— 这是既有行为,spec §2.1 明文容许(从严只在「少认」方向);空容器的
    宿主就是 dict,与上面的非 dict 收口是**两件事**。"""
    for form in (jsonpath, _template_path(jsonpath)):
        if form in universe:
            return True
    if not isinstance(body, dict):
        return False
    if _host_conflict(body, _body_target(jsonpath)):
        return False
    return exists(body, jsonpath)


def _host_conflict(body: Any, target: str) -> bool:
    """``target`` 的路径是否落在**不称职的宿主容器**上 —— 是则不可安全物化。

    引擎 ``_set_at`` 的 FIELD 段遇非 dict 即 ``data={}``、INDEX 段遇非 list 即
    ``data=[]``,故往字符串/数字/别的容器**内部**写值会把整个宿主改形:
    ``$.request_body.note.replace`` 之于 ``{"note":"hello"}`` ⇒ ``note`` 整体
    换成 ``{"replace": v}``;``$.request_body.items[0].replace`` 之于
    ``{"items":["abc"]}`` ⇒ 元素 ``"abc"`` 换成 ``{"replace": v}``。

    分段走 **jsonpath 自己的解析器**的 token(``items[0]`` 是 FIELD+INDEX 两段,
    不是字面键 ``"items[0]"``)—— 与被判的引擎 ``_set_at`` 同一套分段。每段:
    宿主容器类型不符(该段 FIELD 要求 dict / INDEX 要求 list)⇒ **冲突**;
    段**缺失** / 索引**越界** ⇒ **不算冲突**(引擎按类型创建 / 扩展列表);
    末段落点的值本身不判(覆写叶子是 Assign 的正常语义)。

    **规则:走不动 / 无法求值的形状一律算冲突。** 通配(``*``)、过滤器
    (``[?...]``)、递归下降(``..``),以及 ``_parse`` 抛 ``JsonPathError`` 的
    路径,引擎 ``_set_at`` 都对它们抛 ``JsonPathError`` —— **写不进去**。
    物化这种目标只能把「一次跳过 + 告警」换成「一次失败的运行」,没有任何
    收益,故按「不确定就别写」判冲突。**这是明文规则,不是巧合**(它曾经落在
    「不算冲突」那一侧,那是个没被论证过的默认方向)。

    三条**不算冲突**(都是 Assign 的正常语义或可创建情形):
    * target 就是 ``$.request_body`` 本身 —— 整体覆写 body;
    * ``body`` 为 ``None``(无 body)—— Assign 会创建;
    * 路径段**缺失** / 索引**越界** —— 同样由 Assign 创建。

    ``target`` 形如 ``$.request_body.note.replace``:首段是调用点
    (:func:`_body_target` 固定加的前缀)拼接的 FIELD ``request_body``(根
    ``$`` 由 ``_parse`` 吸收),不是 body 的段,**必须剥掉再走**。前缀也按
    token 认,不按字符串切分 —— 否则 ``$.request_body[0].replace`` 这种
    ``[`` 紧贴前缀形态会被误判成「不是 body 内部」而放行,而它恰恰是同类改形
    (「是不是 body 内部」由 walk 回答)。首段不是 ``request_body`` ⇒ 不判、不猜。
    """
    try:
        nodes = _parse(target)
    except JsonPathError:           # 解析不了 ⇒ 走不动 ⇒ 冲突(见上「规则」)
        return True
    if (not nodes or nodes[0].kind is not NodeKind.FIELD
            or nodes[0].value != "request_body"):
        return False                # 不是 body 内部路径 ⇒ 不判、不猜
    rest = nodes[1:]
    if not rest:
        return False                # 恰为 ``$.request_body`` ⇒ 整体覆写
    if body is None:
        return False                # 无 body ⇒ Assign 会创建
    cur: Any = body
    for node in rest:
        if node.kind is NodeKind.FIELD:
            required: type = dict
        elif node.kind is NodeKind.INDEX:
            required = list
        else:                       # 通配 / 过滤 / 递归:走不动 ⇒ 冲突
            return True
        if not isinstance(cur, required):
            return True             # 现存值不是所需容器 ⇒ 引擎会把它整段换掉
        if node.kind is NodeKind.FIELD:
            if node.value not in cur:
                return False        # 缺失 ⇒ 后续由 Assign 创建
            cur = cur[node.value]
        else:
            idx = node.value
            if idx < 0 or idx >= len(cur):
                return False        # 越界 ⇒ 同样由 Assign 创建
            cur = cur[idx]
    return False


def as_step_index(x: Any) -> int | None:
    """stepIndex 归一(Z3):拒 bool;收整数与**整数值浮点**。
    JSON 只有一种数字类型 ⇒ 前端 ``Number.isInteger(1.0)`` 为真,后端必须同判;
    ``true`` 在前端是 false(``Number.isInteger(true)``),后端
    ``isinstance(True, int)`` 却为真 —— 那是分裂,故显式拒绝。"""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return None


def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    body_of: Callable[[int], Any],
    assert_targets_of: Callable[[int], set[str]],
    universe_of: Callable[[int], set[str]] | None = None,
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的**近乎同构**,已知差异见下;
    spec v3 §2):旧形状条目(无 path)/ stepIndex 越界 / path 不落在该步
    **可注入面**(契约声明 ∪ body 现存)上 / override 无匹配。四类 issue 的
    判序与守卫逐条对齐前端 ``registryIssues``。

    可注入面两侧同构(spec v3.1 §2.1 的四子句公式,见
    :func:`injectable_universe`)。**剩余的一处差异**(spec v3.1 §2.1 明文容许
    的 ``exists`` 兜底):后端对本模块多认「空容器本身」(``body={"items":[]}``
    的 ``$.items`` —— 无叶子可生前缀,前端判死),只会**少判死**,方向与
    既有行为一致。

    ``universe_of`` 是**预计算好的**可注入面查表(``Callable[[int], set[str]]``,
    spec §2.1「判定面不耦合网络 I/O」):判定的第 5 参由 ``declared_of``(声明
    路径集)改为 ``universe_of``(该步的 universe)—— 归一与前缀展开都已在
    生产侧由 :func:`injectable_universe` 完成,这里只做成员判定。

    stepIndex 一律过 :func:`as_step_index`(Z3:拒 bool、收整数值浮点),
    与前端 ``Number.isInteger`` 同构。

    ``universe_of`` 缺省 None → 只有 ``{"$"}``(等于 spec v3 的从严行为:
    除根以外一律退回 body 精确存在性)。
    """
    # §5 例外:两侧同为 Optional[Callable] 的缺省形,等价性一眼可判 —— 缺省
    # 查表恰好就是「只认 $ 根」的那张表。
    _universe = universe_of or (lambda si: {"$"})
    issues: list[dict[str, Any]] = []
    path = entry.get("path")
    if not isinstance(path, dict):
        # v2 旧形状(anchor+injection)或残缺条目:全量 issue → skip(spec v3 §8)
        return [{"kind": "legacy-entry"}]
    si = as_step_index(path.get("stepIndex"))
    jp = path.get("jsonpath")
    if si is None or si < 0 or si >= step_count:
        # issue 里记**原始值**(未归一的 path 值)—— 便于前端回显错在哪
        issues.append({"kind": "step-oob", "stepIndex": path.get("stepIndex")})
    elif not isinstance(jp, str) or not _path_resolvable(jp, body_of(si), _universe(si)):
        issues.append({"kind": "path-unresolvable", "stepIndex": si, "jsonpath": jp})
    for a in entry.get("asserts") or []:
        if isinstance(a, dict):
            asi = as_step_index(a.get("stepIndex"))
            if asi is None:
                continue                     # 非数字 stepIndex = 无从寻址,不产生 issue
            if asi < 0 or asi >= step_count:
                issues.append({"kind": "step-oob", "stepIndex": asi})
            elif a.get("mode") == "override" and a.get("target") not in assert_targets_of(asi):
                issues.append({"kind": "override-no-match",
                               "stepIndex": asi, "target": a.get("target")})
    return issues


def compose_injection_scenario(definition: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Assign 直补 + asserts patch(spec v3 §3)。config.vars 零触碰 —
    数据集行值合入在 _compose_scenario(与 Assign 正交叠加,偏离最后生效:
    字段恰为模板串时被字面量整体替换,该 case 内行值对此字段不再起效)。

    **寻址口径与判定侧同构**(C24):`stepIndex` 一律过 :func:`as_step_index`
    (拒 bool、收整数值浮点 —— 与前端 ``Number.isInteger`` 一致),`steps[si]`
    **使用前**校验该元素是 dict;越界 / 非 dict 元素**同待遇:跳过**。
    这不是「dispatcher 已过滤」的重复保险 —— entry_issues 判活的形状仍能
    直达此处(`jsonpath: "$"` 锚在非 dict 步上时判定为活),故这里必须有
    自己的守卫,否则 AttributeError 会掀掉后台 fan-out(零 case + 执行不
    落终态),而不是像越界那样安静跳过。

    **宿主冲突同待遇:跳过 + 告警**(Z1)。target 落在非 dict 宿主内部时
    (``$.request_body.note.replace`` 之于 ``{"note":"hello"}``)物化会让引擎
    ``_set_at`` 把整个宿主改形,故不落 Assign —— 判据见 :func:`_host_conflict`。
    同样不是「判定侧已收口」的重复保险:非 UI 下发(直连 POST /runs、脚本)
    不经前端,且此处是物化的最后一道。不引入新 error code、不让请求失败。

    value 由用户显式编辑,原样覆写不 coerce —— 但引擎 `_resolve_source_value`
    只对**非字符串**直通,两类字符串会被解释:`$.` 前缀串按上下文 JSONPath
    读取(**已补 default/required 兜底**,读不到时仍写字面量);整串 `"${...}"`
    在预处理阶段即被当模板变量读取、**兜不住**(缺变量 → ValueError,有变量
    → 写入 vars 值)。三条边界与理由见 `_assign_strategy`。
    """
    out = copy.deepcopy(definition)
    steps = out.get("steps") or []
    path = entry.get("path")
    if isinstance(path, dict):
        si = as_step_index(path.get("stepIndex"))
        jp = path.get("jsonpath")
        if (si is not None and 0 <= si < len(steps) and isinstance(steps[si], dict)
                and isinstance(jp, str) and jp.startswith("$")):
            target = _body_target(jp)
            # §5 例外:缺 ``request`` 与空 ``request`` 同为「本步无请求」这一
            # 缺省形,在 :func:`_host_conflict` 与 Assign 创建语义下等价。
            body = (steps[si].get("request") or {}).get("body")
            if _host_conflict(body, target):
                logger.warning(
                    "injection entry skipped: 目标路径 {} 落在非 dict 宿主上 "
                    "(物化会改形宿主,target={})", jp, target)
            else:
                steps[si].setdefault("strategy", []).append(
                    _assign_strategy(entry.get("value"), target))
    for a in entry.get("asserts") or []:
        if not isinstance(a, dict):
            continue
        si = as_step_index(a.get("stepIndex"))
        if si is None or si < 0 or si >= len(steps) or not isinstance(steps[si], dict):
            continue
        strat = steps[si].setdefault("strategy", [])
        if a.get("mode") == "override":
            for st in strat:
                if (isinstance(st, dict) and st.get("kind") == "assertion"
                        and st.get("target") == a.get("target")):
                    st["expected"] = a.get("expected")
        else:
            strat.append({"kind": "assertion", "target": a.get("target", ""),
                          "operator": a.get("operator", "eq"), "expected": a.get("expected")})
    return out
