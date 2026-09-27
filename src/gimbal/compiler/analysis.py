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

**输入 = 引用 − 内部产出 − 自带默认**：config.vars 有默认值者视为可选输入
（注入可覆盖）；字面量注入由 UnitDecl.inputs 承担，在 bind 阶段扣减。

纯函数、无副作用；bind（连线）以本模块结果为准。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario
from gimbal.schema.strategy import Extract, Scope

logger = get_logger(__name__)

# ${...} 模板引用（与 utils/jsonpath 的 _TEMPLATE_VAR_RE 同口径）
_TEMPLATE_RE = re.compile(r"\$\{([^{}]+)\}")

# 非 scenario 变量的模板命名空间（预处理 root 的另外两支）
_NON_VAR_PREFIXES = ("service.", "auth.")

# 众所周知由协议调用在 step 内部产出的 scratch 键前缀（$. 引用的内部面）
_INTERNAL_SCRATCH_PREFIXES = (
    "request_", "response_", "duration_ms", "call", "echo_", "scratch",
)


@dataclass
class ScenarioAnalysis:
    """一个 scenario 的静态分析结果。"""
    outputs: set[str] = field(default_factory=set)       # 对外产出（SCENARIO 提升目标）
    inputs: set[str] = field(default_factory=set)        # 需要外部供给的变量名
    var_refs: set[str] = field(default_factory=set)      # 形态1：${var.x}/裸 ${x} 全量引用
    jsonpath_refs: set[str] = field(default_factory=set) # 形态2：$.x 首段（含内部 scratch，未扣除）
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


def _collect_var_refs(scenario: Scenario) -> tuple[set[str], set[str]]:
    """形态 1：收集 ${var.x} / 裸 ${x} 引用。

    返回 (var_refs, bare_refs)。service./auth. 前缀排除。
    """
    var_refs: set[str] = set()
    bare_refs: set[str] = set()
    try:
        dumped = scenario.model_dump(mode="json")
    except Exception:  # noqa: BLE001
        dumped = {"steps": []}
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


def _collect_jsonpath_and_outputs(scenario: Scenario) -> tuple[set[str], set[str]]:
    """形态 2/3 + 输出面：遍历策略。

    - Assign source "$.x..."（STEP 作用域回退 SCENARIO 层）→ x 记 jsonpath_refs
    - Assign source "${x}"（STEP 作用域先 scratch 后 scenario）→ x 记裸名
    - Extract scope != STEP → target 记 outputs
    """
    jsonpath_refs: set[str] = set()
    outputs: set[str] = set()
    for step in scenario.steps:
        for strat in getattr(step, "strategy", []) or []:
            kind = getattr(strat, "kind", None)
            if kind == "assign":
                source = getattr(strat, "source", None)
                if isinstance(source, str) and source.startswith("$."):
                    first = source[2:].split(".", 1)[0].split("[", 1)[0]
                    if first:
                        jsonpath_refs.add(first)
            elif kind == "extract":
                scope = getattr(strat, "scope", Scope.STEP)
                if scope != Scope.STEP:
                    target = getattr(strat, "target", None)
                    if target:
                        outputs.add(target)
    return jsonpath_refs, outputs


def analyze_scenario(scenario: Scenario) -> ScenarioAnalysis:
    """静态分析一个 scenario 的输入/输出面（纯函数）。"""
    var_refs, bare_refs = _collect_var_refs(scenario)
    jsonpath_refs, outputs = _collect_jsonpath_and_outputs(scenario)

    config_vars = set(getattr(scenario.config, "vars", None) or {}.keys())

    # $. 引用中，协议调用内部产出的 scratch 前缀不算外部输入
    external_jsonpath = {
        name for name in jsonpath_refs
        if not any(name == p or name.startswith(p) for p in _INTERNAL_SCRATCH_PREFIXES)
    }

    required = (var_refs | bare_refs | external_jsonpath) - outputs
    # config.vars 提供默认值 → 可选输入（注入可覆盖），不计入必选
    optional = required & config_vars
    inputs = required - config_vars

    return ScenarioAnalysis(
        outputs=outputs,
        inputs=inputs,
        var_refs=var_refs | bare_refs,
        jsonpath_refs=external_jsonpath,
        optional_inputs=optional,
    )
