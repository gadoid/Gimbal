"""dispatch 物化基线生成器(2026-09-05 spec §6-M3 ⑧/§9 ⑧ 基线重钉工具)。

生成 dispatch 物化终值的目录敏感分量六段转储(canonical JSON sort_keys
写出)。回归测试 tests/plate/test_dispatch_baseline.py 经 importlib 加载
本模块 build_dump,与 fixtures/dispatch_baseline.json 逐段全等比对 ——
目录或解析链的任何演进取到「无意识改变 dispatch 物化终值」时即红
(有意漂移闸门);重钉 = 本工具再生成 + 经评审并回 fixture。

M3 A/B 对拍已收口(2026-09-05:切换时点存量值表下新旧树六段全等,
commit b7d522f);旧树侧对照逻辑随对拍收口移除,仅存 git 历史。

批构成(A/B 收口时点同款,由 plate 注册表在线发现):
  * fin 全端点(排序去重)—— 每端点一个合成 step(view_hints.endpoint_id
    锚点 + 空 body),构成「AB 批」场景;
  * Scenario_Test_14_copy.json(36 步真实转储,plate 既有测试同款)。

六段:
  A. endpoints        —— 批身份(端点 id 排序表);
  B. carry_faces      —— 每端点 carry 注入面 {path: type}
                         (field_state_resolution.carry_face 解析链单一实现,
                         场景无增量 → 读穿 = 盖戳面);
  C. carry_injected   —— AB 批每端点 carry 注入后的物化请求体
                         (run_materialize._apply_carry;值表确定性合成:
                         面内每 path 按契约类型给值;--values-from 锚定
                         切换时点存量值表 —— 服务级值表跨端点共享,
                         面差路径恰有同路径值即真实改变物化);
  D. convert_gimbal / convert_platform —— plate /convert 产物
                         (dispatch 链的 plate 调用:校验 + 剥平台视图字段;
                         platform 产物含 endpoints 定面 = M1 消费方 #3);
  E. exports          —— dispatch("gimbal"/"platform", Scenario_Test_14)
                         直接导出产物(与 HTTP convert 同源的真源)。

用法:
    python tools/ab_dispatch_dump.py --out dump.json [--values-from 值表.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src" / "gimbal-plate", REPO / "src" / "gimbal-platform" / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi.testclient import TestClient  # noqa: E402

from gimbal_plate.http import create_app  # noqa: E402

# 解析链单一实现(§3.2)— 本工具只从新树跑(旧树对照已随 A/B 收口移除)
from app.services.field_state_resolution import carry_face  # noqa: E402


# ── 确定性值表(模拟 carry 绑定值;值表存 str,注入按类型强转)────
def carry_value(path: str, ftype: str) -> str:
    if ftype == "integer":
        return "7"
    if ftype == "number":
        return "0.5"
    if ftype == "boolean":
        return "true"
    if ftype == "object":
        return '{"ab": "v"}'
    if ftype == "array":
        return '["ab"]'
    return f"ab:{path}"


def _load_real_scenario() -> dict:
    """Scenario_Test_14_copy.json(plate 既有测试同款预处理)。"""
    raw = json.loads(
        (REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json").read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return raw


def _ab_batch_scenario(eids: list[str]) -> dict:
    """AB 批场景:每端点一个合成 step(锚点 + 空 body,注入后成物化终值)。"""
    return {
        "kind": "scenario",
        "scenarioId": "ab-batch",
        "meta": {
            "name": "ab-batch", "system": ["fin"], "owner": "ab", "author": "ab",
            "description": "", "tags": [], "version": "v0.1.0",
            "requirementRef": [], "module": "ab", "priority": 1,
            "createTime": "2026-09-05T00:00:00Z", "expire": False,
        },
        "resource": {},
        "config": {},
        "steps": [
            {"kind": "step", "description": f"ab:{eid}",
             "api": {"kind": "api", "service": "fin", "method": "POST",
                     "path": "/ab", "headers": {},
                     "view_hints": {"endpoint_id": eid}},
             "request": {"kind": "request", "body": {}},
             "strategy": []}
            for eid in eids
        ],
    }


def build_dump(values: dict[str, str] | None = None) -> dict:
    """生成六段转储;values 给定即锚定值表,None = 按自身面合成。

    回归测试(tests/plate/test_dispatch_baseline.py)经 importlib 加载
    本函数 —— 生成算法单一真源,测试与 CLI 不漂移。
    """
    out: dict = {}

    with TestClient(create_app()) as client:
        # A. 批身份:注册表全端点(排序)
        r = client.get("/api/endpoint/full")
        r.raise_for_status()
        data = r.json()["data"]
        items = data.get("items") if isinstance(data, dict) else data
        eids = sorted(it["id"] for it in items)
        out["endpoints"] = eids

        # B. carry 面(每端点;/full wire → 解析链真源投影)
        faces: dict[str, dict[str, str]] = {}
        for eid in eids:
            item = (client.get(f"/api/endpoint/{eid}/full").json()["data"] or {})["item"]
            decls = ((item.get("request") or {}).get("declarations")) or []
            faces[eid] = carry_face(decls)
        out["carry_faces"] = faces

        # C. carry 注入物化终值(run_materialize 双侧同源;值表确定性合成)
        from app.services.run_materialize import CarryContext, materialize_run_copy
        if values is None:
            values = {}
            for face in faces.values():
                for path, ftype in face.items():
                    values.setdefault(path, carry_value(path, ftype))
        batch = _ab_batch_scenario(eids)
        ctx = CarryContext(
            step_fields={i: faces[eid] for i, eid in enumerate(eids)},
            service_bindings={"fin": values},
            global_defaults={},
        )
        materialized = materialize_run_copy(
            json.loads(json.dumps(batch)),  # 深拷贝隔离(纯函数语义同产线)
            service_bindings={}, resolved_auths=[], built_in_users={},
            carry_context=ctx,
        )
        out["carry_injected"] = {
            eid: (step.get("request") or {}).get("body")
            for eid, step in zip(eids, materialized.get("steps") or [])
        }

        # D. plate /convert 产物(dispatch 链的 plate 调用)
        for consumer in ("gimbal", "platform"):
            resp = client.post("/api/scenario/action/convert",
                               json={"consumer": consumer, "scenario": materialized})
            payload = {"status": resp.status_code}
            if resp.status_code == 200:
                payload["converted"] = resp.json()["data"]["converted"]
            else:
                payload["errors"] = resp.json().get("errors")
            out[f"convert_{consumer}"] = payload

    # E. 直接导出真源(dispatch 装配;真实转储场景)
    from gimbal_plate.export import dispatch as export_dispatch
    from gimbal_plate.schema.scenario import Scenario
    sc = Scenario.model_validate(_load_real_scenario())
    out["exports"] = {
        consumer: export_dispatch(consumer, scenario=sc)
        for consumer in ("gimbal", "platform")
    }

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    # 值表锚定(切换时点存量值表 = 旧面路径集;--values-from 两侧同表):
    # 存量值表只含旧面键。新面若与旧面有差(盖戳违规即差),差路径按表
    # 有无值决定是否注入 — 服务级值表跨端点共享,任何面扩量只要存量表
    # 恰有同路径值即真实改变物化 → 面全等才是切换等价的硬前提。
    ap.add_argument("--values-from",
                    help="JSON {path: value} 值表快照;缺省 = 自身面合成值")
    args = ap.parse_args()
    values = None
    if args.values_from:
        values = {str(k): str(v) for k, v in json.loads(
            Path(args.values_from).read_text(encoding="utf-8")).items()}
    out = build_dump(values)
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=str),
        encoding="utf-8")
    print(f"endpoints={len(out['endpoints'])} "
          f"carry_paths={sum(len(f) for f in out['carry_faces'].values())} -> {args.out}")


if __name__ == "__main__":
    main()
