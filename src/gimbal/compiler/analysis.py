"""compiler/analysis.py — 静态分析：scenario 的输入面与输出面（v2 §静态分析，批次 C）。

这是总案风险登记册第 1 号（"错了不报错、静默错绑"）的正面对象；
**三形态输入面**（与 strategy/builtin/utils.py `_resolve_source_value`
的运行期取值通道一一对应）：

  1. ``${var.x}`` / 裸 ``${x}`` 模板引用 —— 预处理期经 root={service,auth,var}
     解析；``service.*`` / ``auth.*`` 前缀不是 scenario 变量，排除；
  2. ``$.x`` JSONPath（Assign source，STEP 作用域）—— 运行期 scratch 未命中
     时**回退 SCENARIO 层**用同一路径查询（Channels.get_variable 支持
     ``$.x`` 平铺导航）→ 首段 x 记为输入；
  3. 裸名 scratch 查找（Assign source ``${x}`` STEP 作用域先查 scratch、
     再回退 scenario）→ x 记为输入。

**输出面** = scenario 作用域的 extract 目标（scope != STEP 的 Extract 在
运行期 promote 到 SCENARIO 层 channels）—— 即"这个场景对外产出了什么变量"。

**输入 = 引用先于产出 + 非自带默认**（P0-7：按 step 序单遍数据流）：
``_dataflow`` 按 step 顺序遍历，每 step 先收集引用、后收集产出；
某名字在进入 ``produced`` 之前被引用即计输入——晚到的产出不再抵消早前
的引用（旧实现 ``required = 引用 - outputs`` 是无序集合差，先引用后产出
的名字被静默吞掉）。协议内部键（``_PROTOCOL_PRODUCED_KEYS``，**精确键名**）
自场景开始即可视为已产出；P1-8：不再按前缀 startswith 匹配，业务变量
``callbackUrl`` 之类不被 ``call`` 前缀误伤。config.vars 有默认值者视为
可选输入（注入可覆盖）；字面量注入由 UnitDecl.inputs 承担，在 bind 阶段扣减。

纯函数、无副作用；bind（连线）以本模块结果为准。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario
from gimbal.schema.strategy import Scope

logger = get_logger(__name__)

# ${...} 模板引用（与 utils/jsonpath 的 _TEMPLATE_VAR_RE 同口径）
_TEMPLATE_RE = re.compile(r"\$\{([^{}]+)\}")

# 非 scenario 变量的模板命名空间（预处理 root 的另外两支）
_NON_VAR_PREFIXES = ("service.", "auth.")

# 协议调用在每个 step 内产出的 scratch 键（$. 引用的内部面）。
# P1-8：**精确键名**匹配——旧版 _INTERNAL_SCRATCH_PREFIXES 按 startswith
# 前缀匹配（"call"/"response_"/"echo_"/…），callbackUrl / caller_no 这类
# 业务变量会被 "call" 前缀误吞成内部键、静默丢输入。内部面收敛为一组成
# 熟的协议归一树键；其余名字一律按外部引用对待。
# v2.1 批次 F 终态：旧键 response_body/response_status/duration_ms 已
# 退役（无人写入）——不再列为内部键，未迁移存量 case 的残留引用按外部
# 引用显形（jsonpath_refs 可见），而不是被静默吞成内部面。
_PROTOCOL_PRODUCED_KEYS = frozenset({
    "call",              # $.call.request/response... 协议归一树根
                         # (残留 #5:请求体通道并入 $.call.request.body 子树)
})


@dataclass
class ScenarioAnalysis:
    """一个 scenario 的静态分析结果。"""
    outputs: set[str] = field(default_factory=set)       # 对外产出（SCENARIO 提升目标）
    inputs: set[str] = field(default_factory=set)        # 需要外部供给的变量名
    var_refs: set[str] = field(default_factory=set)      # 形态1：${var.x}/裸 ${x} 全量引用
    jsonpath_refs: set[str] = field(default_factory=set) # 形态2：$.x 首段（外部面：已扣精确协议内部键）
    optional_inputs: set[str] = field(default_factory=set)  # config.vars 提供默认值的

    def summary(self) -> dict:
        return {
            "outputs": sorted(self.outputs),
            "inputs": sorted(self.inputs),
            "optional_inputs": sorted(self.optional_inputs),
            "var_refs": sorted(self.var_refs),
            "jsonpath_refs": sorted(self.jsonpath_refs),
        }


def _walk_strings(node: Any):
    """递归遍历 dict/list/标量结构，yield 所有字符串（pydantic 先 model_dump）。"""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_strings(item)


def _dump_safely(node: Any) -> dict:
    """model_dump 的防御包装：dump 失败按空结构处理（分析不因 schema 异常炸掉）。"""
    try:
        return node.model_dump(mode="json")
    except Exception:  # noqa: BLE001
        return {}


def _collect_template_refs(dumped: Any) -> tuple[set[str], set[str]]:
    """形态 1：从已 dump 的结构收集 ${var.x} / 裸 ${x} 引用。

    返回 (var_refs, bare_refs)。service./auth. 前缀排除；其它带点命名空间
    （未来扩展）暂不计入输入面。
    """
    var_refs: set[str] = set()
    bare_refs: set[str] = set()
    for s in _walk_strings(dumped):
        for m in _TEMPLATE_RE.finditer(s):
            ref = m.group(1).strip()
            if ref.startswith(_NON_VAR_PREFIXES):
                continue
            if ref.startswith("var."):
                name = ref[len("var."):].split(".", 1)[0]
                if name:
                    var_refs.add(name)
            elif "." in ref:
                # 其它带点前缀（未来命名空间）暂不计入输入面
                continue
            else:
                bare_refs.add(ref)
    return var_refs, bare_refs


def _step_jsonpath_refs(step: Any) -> set[str]:
    """形态 2：step 内 Assign source ``$.x...`` 的首段 x（含 ``$.x[0]`` 下标形式）。"""
    refs: set[str] = set()
    for strat in getattr(step, "strategy", []) or []:
        if getattr(strat, "kind", None) == "assign":
            source = getattr(strat, "source", None)
            if isinstance(source, str) and source.startswith("$."):
                first = source[2:].split(".", 1)[0].split("[", 1)[0]
                if first:
                    refs.add(first)
    return refs


def _step_productions(step: Any) -> set[str]:
    """step 的产出：scope != STEP 的 Extract 提升目标（运行期 promote 到
    SCENARIO 层 channels，对后续 step 与连线可见）。STEP 作用域提取只写
    step 本地 scratch，不跨 step 可见，不计产出。"""
    produced: set[str] = set()
    for strat in getattr(step, "strategy", []) or []:
        if getattr(strat, "kind", None) == "extract":
            scope = getattr(strat, "scope", Scope.STEP)
            if scope != Scope.STEP:
                target = getattr(strat, "target", None)
                if target:
                    produced.add(target)
    return produced


def _dataflow(steps: list) -> tuple[set[str], set[str]]:
    """按 step 序单遍数据流（P0-7）。

    ``produced`` 初始含协议内部键（``_PROTOCOL_PRODUCED_KEYS`` 精确键名）；
    每个 step **先**收集其引用，**后**收集该 step 的产出（Extract 提升目标）
    入 ``produced``。引用先于产出者不被晚到的产出抵消。

    模板与 scratch 两条通道语义不同（上轮评审 #3）：
      - ``${x}`` 模板引用在**预处理期一次性渲染**（root=var/auth/service），
        场景内的 Extract 产出那时尚不存在——**一律计外部输入**（可由
        config.vars 默认/注入/上游单元连线供给），不参与数据流抵消；
      - ``$.x`` scratch 引用是**运行期**通道，可被本场景前序 Extract 产出
        抵消（引用时点未在 produced 中才计 required）。

    返回 (required, outputs)：
      required —— 需要外部供给的名字（协议内部键已在初始 produced，天然不算）
      outputs  —— SCENARIO 提升目标终态集合（对外输出面）
    """
    produced = set(_PROTOCOL_PRODUCED_KEYS)
    required: set[str] = set()
    outputs: set[str] = set()
    for step in steps:
        var_refs, bare_refs = _collect_template_refs(_dump_safely(step))
        # 模板引用：预处理期渲染,不被场景内产出抵消（一律外部输入）
        required |= var_refs | bare_refs
        # scratch 引用：运行期通道,数据流抵消
        required |= _step_jsonpath_refs(step) - produced
        outs = _step_productions(step)
        produced |= outs
        outputs |= outs
    return required, outputs


def analyze_scenario(scenario: Scenario) -> ScenarioAnalysis:
    """静态分析一个 scenario 的输入/输出面（纯函数）。"""
    var_refs: set[str] = set()
    bare_refs: set[str] = set()
    jsonpath_refs: set[str] = set()

    # steps 之外的声明段（config/meta/resource…）在预处理期先于一切 step 生效：
    # 其模板引用视为 step 0 引用（仅协议内部键不算外部输入），保持全量引用面。
    preamble = {k: v for k, v in _dump_safely(scenario).items() if k != "steps"}
    preamble_var, preamble_bare = _collect_template_refs(preamble)
    var_refs |= preamble_var
    bare_refs |= preamble_bare

    for step in scenario.steps:
        step_var, step_bare = _collect_template_refs(_dump_safely(step))
        var_refs |= step_var
        bare_refs |= step_bare
        jsonpath_refs |= _step_jsonpath_refs(step)

    required, outputs = _dataflow(scenario.steps)
    # step 0（声明段）引用先于一切产出：仅扣协议内部键
    required |= (preamble_var | preamble_bare) - _PROTOCOL_PRODUCED_KEYS

    # $. 引用报告外部面：扣精确协议内部键（P1-8：不再按前缀吞 callbackUrl）
    jsonpath_refs -= _PROTOCOL_PRODUCED_KEYS

    config_vars = set(getattr(scenario.config, "vars", None) or {}.keys())
    # config.vars 提供默认值 → 可选输入（注入可覆盖），不计入必选
    optional = required & config_vars
    inputs = required - config_vars

    return ScenarioAnalysis(
        outputs=outputs,
        inputs=inputs,
        var_refs=var_refs | bare_refs,
        jsonpath_refs=jsonpath_refs,
        optional_inputs=optional,
    )
