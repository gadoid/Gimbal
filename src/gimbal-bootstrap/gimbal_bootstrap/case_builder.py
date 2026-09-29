"""用例 YAML → plate Scenario definition。

definition 必须是能过 plate /convert 的合法 Scenario。实测最小必填集：
scenarioId / meta(11 项) / config.services / config.timePolicy / resource /
steps[].call / steps[].request / steps[].strategy。

**每一步必须声明 `endpoint`**（契约里的端点 id），生成器据此写
`call.view_hints.endpoint_id`。这不是可选的元数据，而是用例组织这一侧**唯一**
能把字段面送到编辑面的通道：前端 `stepEndpointId()` 只认这个 key，拿不到就
不拉 plate 的 `/full`，`requestNodes` 为空，body 退回裸 JSON 文本框 +
「该接口未声明请求字段契约」提示。平台自带的「从接口目录添加」路径写的就是这个
key；自举是手搓 definition，绕开了那条路径，所以必须自己写 —— 漏了就是用户
看到的那句提示。
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from typing import Any

SERVICE = "platform-service"
SERVICE_URL = "http://127.0.0.1:8000"
FIXED_CREATE_TIME = "2026-09-28T00:00:00Z"

SCENARIO_ID_RE = re.compile(r"^sc-[a-z0-9-]+$")

# 路径占位符：契约侧是 OpenAPI 的模板态 `{scenario_id}`，用例侧是运行态
# `${sb.scenario_id}` —— 两者是同一条路由，只是变量来源不同，比路由时先归一。
_PATH_PARAM_RE = re.compile(r"\$\{[^}]*\}|\{[^}]*\}")


def path_shape(path: str) -> str:
    """路径归一：把两种占位符都压成 `{p}`，只留下路由骨架。

    用于「这条 step 打的是不是它声明的那个端点」的判据。用运行态 path 去撞模板
    态契约，永远对不上 —— 不是路由错了，是形态不同。
    """
    return _PATH_PARAM_RE.sub("{p}", path)


def _load_contract_index() -> dict[str, Any]:
    """plate 已装机的契约定义，按 endpoint id 索引。

    进程内读，不走 HTTP：走 HTTP 拿到的是**常驻 plate 进程的旧版本**（实测它
    还停在 115 个端点，而 checkout 里已经是 126 个），拿它当门会放过已漂移的
    契约。仓内相对路径 import，与 tests/conftest.py 同一个理由 —— 契约验证该
    贴着这份 checkout 跑，而不是某个已安装的旧版本。
    """
    plate_dir = Path(__file__).resolve().parents[2] / "gimbal-plate"
    if str(plate_dir) not in sys.path:
        sys.path.insert(0, str(plate_dir))
    from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS

    return {ep.id: ep for ep in ALL_ENDPOINTS}


def __getattr__(name: str) -> Any:
    """`CONTRACT_INDEX` 惰性装载（PEP 562）。

    不在 import 期装：case_builder 的主职责是纯 dict 组装，让它一 import 就
    去拉 plate 的整份契约目录，是把「生成用例」和「校验用例」耦成了一件事。
    第一次真正用到时才装，装完缓存住。
    """
    if name == "CONTRACT_INDEX":
        index = _load_contract_index()
        globals()["CONTRACT_INDEX"] = index
        return index
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _resolve_endpoint(step: dict[str, Any], where: str) -> str:
    """校验 step 声明的 endpoint，并返回它的 id。

    两条门，缺一不可：
    - **存在**：id 必须在已装机的契约里。平台下掉一条路由而用例还指着它时，
      生成期就响 —— 否则场景建得起来、跑得起来，只是页面上 body 变成裸 JSON，
      看不出成因。
    - **route 对得上**：id 存在但指向另一条路由，比不存在更隐蔽：用例绿、断言
      对，页面上挂的却是别的接口的字段面。
    """
    eid = step.get("endpoint")
    if not eid:
        raise ValueError(
            f"{where}: step 没有声明 endpoint —— 生成的 call 就不会有 "
            f"view_hints.endpoint_id，编辑器里 body 会退回裸 JSON 文本框"
        )
    ep = _load_contract_index().get(eid)
    if ep is None:
        raise ValueError(
            f"{where}: endpoint {eid!r} 不在 plate 已装机的契约里"
            f"（平台可能已下掉这条路由，或用例写错了 id）"
        )
    if (
        ep.api.method != step["method"]
        or path_shape(ep.api.path) != path_shape(step["path"])
    ):
        raise ValueError(
            f"{where}: endpoint {eid!r} 的 route 与该 step 对不上"
            f"（{ep.api.method} {ep.api.path} vs {step['method']} {step['path']}）"
        )
    return eid


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def _username_slug(text: str) -> str:
    """平台 RegisterIn.username = ^[A-Za-z0-9_]+$ —— 比 _slug 还窄：
    连字符和点都不收。"""
    return re.sub(r"[^A-Za-z0-9_]+", "", text)


def _render(value: Any, subs: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, repl in subs.items():
            value = value.replace("${" + key + "}", repl)
        return value
    if isinstance(value, dict):
        return {k: _render(v, subs) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, subs) for v in value]
    return value


def build_definition(
    case: dict,
    *,
    sb_username: str,
    sb_password: str = "",
    run_token: str = "",
    new_username: str = "",
    new_password: str = "",
) -> dict:
    """用例 YAML → plate Scenario definition。

    **管理员口令不进 definition。** definition 就是 POST /api/scenarios 的
    body，平台把它存进 composer_scenario.payload，每次运行再深拷贝进
    execution_snapshots —— 那张表本仓库里没人清理。管理员口令从这条路进去
    等于把平台交出去，而且绕开了「口令不入库」那条原则。

    所以这里根本没有 `${sb.password}` 这个占位符：验 register/login 用的是
    一次性账号，口令由编排器当场随机生成（`new_password`），跟管理员口令
    无关，跑完就把那个账号删掉。
    """
    base = _slug(case["id"])
    token = _slug(run_token)
    scenario_id = f"sc-{base}-{token}" if token else f"sc-{base}"
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ValueError(f"scenario_id 不合规: {scenario_id!r}")

    subs = {
        "sb.username": sb_username,
        "sb.scenario_id": scenario_id,
        # 一次性账号：验 register / login 端点本身。不能复用 sb.username ——
        # 那是编排器已经建好并提权过的那个，同名必 409。必须由编排器按
        # **轮次**传进来：按用例派生的话，注册的账号和后续登录的账号就
        # 不是同一个。
        "sb.new_username": new_username
        or "sb_" + _username_slug(token or uuid.uuid4().hex[:6]),
        "sb.new_password": new_password,
    }

    steps: list[dict[str, Any]] = []
    for step in case["steps"]:
        service = step.get("service", SERVICE)
        if service != SERVICE:
            raise ValueError(
                f"只允许 service={SERVICE}，收到 {service!r} —— 自举只打平台自己"
            )
        strategy: list[dict[str, Any]] = []
        extract = step.get("extract")
        if extract:
            strategy.append({
                "kind": "extract",
                "expression": _render(extract["expr"], subs),
                "target": extract["target"],
                "scope": "scenario",
                "required": extract.get("required", True),
            })
        for a in step.get("asserts", []):
            strategy.append({
                "kind": "assertion",
                "target": _render(a["target"], subs),
                "operator": a["operator"],
                "expected": _render(a.get("expected"), subs),
                "message": a.get("message", case.get("name", "")),
                "soft": a.get("soft", False),
            })
        if not strategy:
            raise ValueError(f"step 至少要有 1 个 strategy（case {case['id']}）")

        headers = {"Content-Type": "application/json"}
        if step.get("auth", True):
            headers["Authorization"] = "Bearer ${auth.sb.token}"

        eid = _resolve_endpoint(step, f"case {case['id']}")

        steps.append({
            "kind": "step",
            # call 是唯一调用形态（v2.1 批次 F 退役了 step.api）。
            # plate 的 Step._reject_api_form 在 validate 期显式拒 api 形态，
            # 存量文件的迁移见 scripts/migrate_legacy_case.py；这里是生成器，
            # 直接按新形态产出，不走迁移。
            "call": {
                "kind": "call",
                "protocol": "http",
                "service": SERVICE,
                "method": step["method"],
                "path": _render(step["path"], subs),
                "headers": headers,
                # 接口身份：编辑器据此拉 plate 的 /full 拿字段面。缺了它，
                # body 就是裸 JSON 文本框（见模块 docstring）。
                "view_hints": {"endpoint_id": eid},
            },
            "request": {
                "kind": "request",
                "body": _render(step.get("body", {}), subs),
            },
            "strategy": strategy,
        })

    return {
        "kind": "scenario",
        "scenarioId": scenario_id,
        "meta": {
            "name": case.get("name", case["id"]),
            "description": case.get("description", ""),
            "module": "self-bootstrap",
            "priority": 1,
            "author": sb_username,
            "owner": sb_username,
            "tags": case.get("tags", ["smoke"]),
            "version": "1.0.0",
            "createTime": FIXED_CREATE_TIME,
            "expire": False,
            "requirementRef": [],
            "system": ["platform"],
        },
        "config": {
            "services": {SERVICE: SERVICE_URL},
            "users": {},
            "timePolicy": {"kind": "record"},
            "vars": {},
        },
        "resource": {},
        "steps": steps,
    }
