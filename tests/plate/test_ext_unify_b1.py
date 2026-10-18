"""批1 验收用例(归一方案 v1.0 §3.1 / 批1 小设计 §10 / 实施计划 §3)。

覆盖:代际与错误码集合不变、列表行带 kind 反向断言、check 四规则正反例、
parse_ref reason(读契约 fixture)、裸线对齐拒(B3 已翻)、resolve 前置分流、
_needs_root、状态码分域(取数 400 带 reason / convert 422 / resolve 422)、
双向绑定、/healthz 透出标识、定义标识稳定性。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gimbal_plate.dialect.canonical import integration_system_hash
from gimbal_plate.dialect.validation import collect_system_tree, validate_system_tree
from gimbal_plate.http import create_app
from gimbal_plate.http.envelope import ErrorCode
from gimbal_plate.loader import load_registry
from gimbal_plate.release.read import parse_ref
from gimbal_plate.release.release import M2_VERSION

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "ref-decl-domain.json"

# b1 验收:错误码集合不变(批1 只加 reason,不加 ErrorCode)
_ERROR_CODES_FROZEN = {
    "dim_not_found", "dim_item_not_found", "system_not_found", "invalid_action",
    "registry_unavailable", "internal_error", "admin_not_implemented",
    "redacted_sensitive", "invalid_query_param", "release_not_found",
    "release_corrupt", "release_m2_incompatible", "invalid_ref",
    "version_undeclared", "endpoint_not_in_release", "header_conflicts_binding",
    "binding_field_in_storage", "ref_required", "m2_not_found",
}


def _sys_md(system: str, *, kind_line: str = "kind: integration",
            fm_extra: str = "", services: str | None = None) -> str:
    body = services or f"""review: reviewed
name: {system}-service
title: {system}
version: 1.0.0
{kind_line}"""
    return f"""---
type: system
system: {system}
{fm_extra}---

# {system}

```gimbal:system
{body}
```
"""


def _ep_md(system: str, name: str, *, path: str = "/list",
           review: str = "reviewed", desc: str = "d",
           extra: str = "") -> str:
    return f"""---
id: {system}.a.{name}
type: endpoints
system: {system}
---

# {name}

```gimbal:endpoint
{'review: ' + review + chr(10) if review else ''}id: {system}.a.{name}
system: {system}
service: {system}-service
name: {name}
description: {desc}
binding:
  protocol: http
  method: GET
  path: {path}{extra}
responses:
  '200': {{}}
```
"""


def _integration_repo(tmp_path: Path, *, system: str = "jira") -> Path:
    root = tmp_path / "sys"
    s = root / system
    (s / "endpoints").mkdir(parents=True)
    (s / "system.md").write_text(_sys_md(system), encoding="utf-8")
    (s / "endpoints" / "list.md").write_text(_ep_md(system, "list"), encoding="utf-8")
    return root


def _scenario(endpoint: str, plate: dict[str, str], system: str = "jira") -> dict:
    return {
        "kind": "scenario", "scenarioId": "sc-b1", "resource": {}, "config": {},
        "meta": {"name": "n", "system": [system], "plate": plate},
        "steps": [{"kind": "step", "endpoint": endpoint,
                   "call": {"kind": "call", "service": f"{system}-service"},
                   "request": {"kind": "request", "body": {}}, "strategy": []}],
    }


def _app_for(root: Path) -> TestClient:
    return TestClient(create_app(registry=load_registry([root])))


# ── 契约 fixture(两侧各读同一份;plate 侧断言) ─────────────────────

class TestContractFixture:
    def test_valid_categories(self):
        mapping = {"WORKING": "working", "INTEGRATION": "integration",
                   "PIN": "revision"}
        for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["valid"]:
            assert parse_ref(case["ref"])[0] == mapping[case["category"]], case

    def test_invalid_reasons(self):
        from gimbal_plate.release.read import ReleaseReadError

        for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["invalid"]:
            with pytest.raises(ReleaseReadError) as ei:
                parse_ref(case["ref"])
            assert ei.value.code == "invalid_ref", case
            assert ei.value.reason == case["reason"], case

    def test_bare_line_keeps_line_kind(self):
        """返回值形状不变:裸线在 parse_ref(取数域)保留 line-kind;
        声明域拒绝由声明闸给出(fixture 的 declaration_reason 不在 parse_ref 层)。"""
        for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["declaration_only"]:
            kind, _line, n = parse_ref(case["ref"])
            assert (kind, n) == ("line", None), case


# ── 不变量:代际 / 错误码集合 ──────────────────────────────────────

class TestInvariants:
    def test_error_code_set_unchanged(self):
        assert {m.value for m in ErrorCode} == _ERROR_CODES_FROZEN

    def test_generations_unchanged(self):
        from gimbal.schema import M2_GENERATION

        assert M2_GENERATION == 2 and M2_VERSION == "2"


# ── 列表行带 kind(全量,不得过滤) ─────────────────────────────────

class TestListKindRows:
    def test_integration_rows_carry_kind(self, tmp_path):
        root = _integration_repo(tmp_path)
        with _app_for(root) as c:
            eps = c.get("/api/endpoint").json()["data"]["items"]
            svcs = c.get("/api/service").json()["data"]["items"]
            sysr = c.get("/api/system").json()["data"]["items"]
        assert eps and all(r.get("kind") == "integration" for r in eps)
        assert svcs and all(r.get("kind") == "integration" for r in svcs)
        assert sysr and sysr[0]["kind"] == "integration"

    def test_real_systems_default_sut(self, http_client):
        rows = http_client.get("/api/service").json()["data"]["items"]
        assert rows and all(r["kind"] == "sut" for r in rows)


# ── plate check 四规则(正反例) ───────────────────────────────────

class TestCheckRules:
    def _check(self, tmp_path: Path, system: str, *, sys_md: str, eps: list[str]):
        d = tmp_path / f"s{len(list(tmp_path.iterdir()))}"
        s = d / system
        (s / "endpoints").mkdir(parents=True)
        (s / "system.md").write_text(sys_md, encoding="utf-8")
        for i, ep in enumerate(eps):
            (s / "endpoints" / f"e{i}.md").write_text(ep, encoding="utf-8")
        return validate_system_tree(s)

    def test_rule1_mixed_kinds_blocking(self, tmp_path):
        # 两个 gimbal:system 块(信封 review 行与 list 载荷不兼容,双块写)
        md = f"""---
type: system
system: sys
---

# sys

```gimbal:system
review: reviewed
name: j1
title: a
version: 1.0.0
kind: integration
```

```gimbal:system
review: reviewed
name: j2
title: b
version: 1.0.0
```
"""
        report = self._check(tmp_path, "sys", sys_md=md, eps=[_ep_md("sys", "a")])
        assert any("kind 不一致" in f.message for f in report.blocking)

    def test_rule2_line_fields_blocking(self, tmp_path):
        report = self._check(tmp_path, "sys", sys_md=_sys_md(
            "sys", fm_extra="line: '1.0'\n"), eps=[_ep_md("sys", "a")])
        assert any("不得声明版本线字段" in f.message for f in report.blocking)

    def test_rule2_line_name_reserved(self, tmp_path):
        report = self._check(tmp_path, "sys", sys_md=_sys_md(
            "sys", fm_extra="line: 'integration'\n"), eps=[_ep_md("sys", "a")])
        assert any("不得命名为 integration" in f.message for f in report.blocking)

    def test_rule3_draft_is_warning_only(self, tmp_path):
        report = self._check(tmp_path, "sys", sys_md=_sys_md("sys"), eps=[
            _ep_md("sys", "a", review="draft")])
        assert any("draft" in f.message for f in report.warnings)
        assert not any("draft" in f.message for f in report.blocking)

    def test_rule4_query_views_blocking(self, tmp_path):
        ep = _ep_md("sys", "a", extra="""
query_views:
  - name: qv
    items: '$.data[*]'
    label: name""")
        report = self._check(tmp_path, "sys", sys_md=_sys_md("sys"), eps=[ep])
        assert any("query_views" in f.message for f in report.blocking)

    def test_clean_integration_passes(self, tmp_path):
        report = self._check(tmp_path, "sys", sys_md=_sys_md("sys"),
                             eps=[_ep_md("sys", "a")])
        assert not report.blocking


# ── resolve 前置分流 / _needs_root / 状态码分域 / healthz ───────────

class TestResolveAndDomains:
    def test_resolve_integration_prefiltered(self, tmp_path):
        root = _integration_repo(tmp_path)
        app = create_app(registry=load_registry([root]))
        with TestClient(app) as c:
            app.state.integration_definitions = {"jira": "abc123"}
            r = c.post("/api/system/action/resolve",
                       json={"meta_plate": {"jira": "integration"},
                             "endpoints": {"jira": ["jira.a.list"]}})
        assert r.status_code == 200
        assert r.json()["data"]["item"]["jira"]["effective"] == "integration@abc123"

    def test_resolve_integration_without_state_bare(self, tmp_path):
        root = _integration_repo(tmp_path)
        app = create_app(registry=load_registry([root]))
        with TestClient(app) as c:
            app.state.integration_definitions = {}
            r = c.post("/api/system/action/resolve",
                       json={"meta_plate": {"jira": "integration"}, "endpoints": {}})
        assert r.json()["data"]["item"]["jira"]["effective"] == "integration"

    def test_resolve_record_value_422(self, tmp_path):
        root = _integration_repo(tmp_path)
        app = create_app(registry=load_registry([root]))
        with TestClient(app) as c:
            r = c.post("/api/system/action/resolve",
                       json={"meta_plate": {"jira": "integration@x"}, "endpoints": {}})
        assert r.status_code == 422
        err = r.json()["error"]
        assert err["code"] == "invalid_ref"
        assert err["details"]["reason"] == "record_value"

    def test_convert_integration_needs_no_root(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PLATE_ARTIFACTS_PATH", raising=False)
        root = _integration_repo(tmp_path)
        with _app_for(root) as c:
            r = c.post("/api/scenario/action/convert",
                       json={"consumer": "gimbal",
                             "scenario": _scenario(
                                 "jira.a.list", {"jira": "integration"})})
        assert r.status_code == 200, r.text

    def test_fetch_route_invalid_ref_400_with_reason(self, tmp_path):
        """取数域:?ref=integration@x → 400(状态码不动)+ details.reason 转发。"""
        root = _integration_repo(tmp_path)
        with _app_for(root) as c:
            r = c.get("/api/systems/jira/endpoint/jira.a.list/full"
                      "?ref=integration@x")
        assert r.status_code == 400, r.text
        err = r.json()["error"]
        assert err["code"] == "invalid_ref"
        assert err["details"]["reason"] == "record_value"

    def test_binding_violation_sut_declares_integration(self, http_client):
        """双向绑定:sut 系统(fin)声明 integration → 422(无 reason)。"""
        sc = _scenario("fin.a.query_balance", {"fin": "integration"}, system="fin")
        r = http_client.post("/api/scenario/action/convert",
                             json={"consumer": "gimbal", "scenario": sc})
        assert r.status_code == 422, r.text
        err = r.json()["error"]
        assert err["code"] == "invalid_ref"
        assert "kind" in err["message"] and "integration" in err["message"]

    def test_healthz_owned_mode_defs(self, tmp_path, monkeypatch):
        root = _integration_repo(tmp_path)
        monkeypatch.setenv("PLATE_SYSTEMS_PATH", str(root))
        with TestClient(create_app()) as c:
            body = c.get("/healthz").json()
        assert set(body["integration_definitions"]) == {"jira"}
        assert "git_head" in body


# ── 定义标识稳定性(D-L) ──────────────────────────────────────────

class TestDefinitionIdentityStability:
    def _hash(self, root: Path) -> str:
        reg = load_registry([root])
        return integration_system_hash(
            list(reg.iter_endpoints_for_system("jira")))

    def test_stability(self, tmp_path):
        root = _integration_repo(tmp_path)
        h0 = self._hash(root)
        ep_file = root / "jira" / "endpoints" / "list.md"
        txt = ep_file.read_text(encoding="utf-8")
        # 仅改 description(纯展示字段)→ 不变
        ep_file.write_text(txt.replace("description: d", "description: changed"),
                           encoding="utf-8")
        assert self._hash(root) == h0
        # 改 binding path → 必变
        ep_file.write_text(txt.replace("path: /list", "path: /list2"),
                           encoding="utf-8")
        assert self._hash(root) != h0
        # 增端点(id 集合进聚合输入)→ 必变
        (root / "jira" / "endpoints" / "x.md").write_text(
            _ep_md("jira", "x"), encoding="utf-8")
        h2 = self._hash(root)
        assert h2 != h0
        # 幂等:重复计算同值
        assert self._hash(root) == h2
