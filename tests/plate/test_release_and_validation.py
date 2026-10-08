"""批次 B 测试：校验引擎 + release 冻结 + gaps（F/T/S/C、8v、内容寻址）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.dialect import EndpointSpec, Statement, Term, parse_markdown
from gimbal_plate.dialect.gaps import gap_items
from gimbal_plate.dialect.validation import (
    ValidationReport,
    load_types,
    validate_consistency,
    validate_deliverable,
    validate_references,
    validate_terms,
)
from gimbal_plate.release.release import _call_projection, release_system


def _mk_ep(**over) -> EndpointSpec:
    base = dict(
        id="t.svc.ping", system="t", service="svc", name="ping",
        binding={"protocol": "http", "method": "GET", "path": "/ping"},
        responses={"200": {}},
    )
    base.update(over)
    return EndpointSpec.model_validate(base)


class TestValidationEngine:
    def test_f1_unknown_type_and_block(self, tmp_path: Path) -> None:
        md = tmp_path / "a.md"
        md.write_text("---\ntype: nope\n---\n```gimbal:term\nid: entity:x\nlabel: X\n```\n", encoding="utf-8")
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        report = validate_deliverable(d, types=load_types())
        rules = {f.rule for f in report.blocking}
        assert "F1" in rules

    def test_f2_required_step(self, tmp_path: Path) -> None:
        md = tmp_path / "s.md"
        md.write_text(
            "---\ntype: user_story\n---\n```gimbal:statement\nid: st.x\nkind: note\n```\n正文\n",
            encoding="utf-8")
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        report = validate_deliverable(d, types=load_types())
        assert any(f.rule == "F2" for f in report.blocking)

    def test_s1_slot_kinds_and_required(self) -> None:
        # rule 缺 about + violation 槽放了 cap kind
        st = Statement(id="st.bad", kind="rule",
                       slots={"violation": "cap:user.delete"})
        d = _deliverable_with_statement(st)
        report = validate_deliverable(d, types=load_types())
        rules = [f.rule for f in report.blocking]
        assert "S1" in rules

    def test_s3_transition_same_attr(self) -> None:
        st = Statement(id="st.t", kind="transition",
                       slots={"cap": "cap:o.run", "from": "value:o.s.a",
                              "to": "value:o.s.b"})
        d = _deliverable_with_statement(st)
        report = validate_deliverable(d, types=load_types())
        assert not [f for f in report.blocking if f.rule == "S3"]
        st2 = Statement(id="st.t2", kind="transition",
                        slots={"cap": "cap:o.run", "from": "value:o.s.a",
                               "to": "value:o.r.b"})
        report2 = validate_deliverable(_deliverable_with_statement(st2), types=load_types())
        assert any(f.rule == "S3" for f in report2.blocking)

    def test_t1_term_grammar_and_common_clash(self) -> None:
        good = Term(id="cap:user.delete", label="删")
        bad_depth = Term(id="value:user.role", label="深度错")
        report = ValidationReport()
        validate_terms([good, bad_depth], system_id="t",
                       common_ids={"cap:user.delete"}, report=report)
        rules = [f.rule for f in report.blocking]
        assert "T1" in rules  # 语法 + common 重名

    def test_t2_parent_missing(self) -> None:
        orphan = Term(id="attr:ghost.role", label="孤儿")
        report = validate_terms([orphan], system_id="t")
        assert any(f.rule == "T2" for f in report.blocking)

    def test_t3_replaced_by_rules(self) -> None:
        chain = [
            Term(id="entity:user", label="用户"),
            Term(id="attr:user.role", label="角色"),
            Term(id="value:user.role.admin", label="管理员",
                 status="deprecated", replaced_by="value:user.role.root"),
            Term(id="value:user.role.root", label="root"),
        ]
        r = validate_terms(chain, system_id="t")
        assert not r.blocking, [f.message for f in r.blocking]
        cycle = [
            Term(id="entity:x", label="x"),
            Term(id="attr:x.y", label="y"),
            Term(id="value:x.y.a", label="a", replaced_by="value:x.y.b"),
            Term(id="value:x.y.b", label="b", replaced_by="value:x.y.a"),
        ]
        r2 = validate_terms(cycle, system_id="t")
        assert any(f.rule == "T3" for f in r2.blocking)


    def test_s2_reference_resolution(self) -> None:
        ep = _mk_ep(capability="cap:none.such")
        report = validate_references([ep], [], {})
        assert any(f.rule == "S2" and f.severity == "blocking" for f in report.findings)
        dep = Term(id="cap:old.x", label="旧", status="deprecated",
                   replaced_by="cap:new.x")
        ep2 = _mk_ep(capability="cap:old.x")
        report2 = validate_references([ep2], [], {"cap:old.x": dep})
        assert any(f.rule == "S2" and f.severity == "warning" for f in report2.findings)

    def test_c1_inconsistent_cap_sets(self) -> None:
        # 槽位形态与生产一致(评审 R1):rule 无 cap 槽(S1 白名单
        # about/before/violation),其 cap 关联 = about 为 cap 类词条;
        # outcome 片段的 cap 关联 = cap 槽。
        s1 = Statement(id="st.1", kind="rule",
                       slots={"about": "cap:a.down",
                              "violation": "outcome:u.last"})
        s2 = Statement(id="st.2", kind="outcome",
                       slots={"cap": "cap:b.del", "outcome": "outcome:u.last"})
        s1._source, s2._source = "prd.md", "endpoints.md"  # 不同来源
        report = validate_consistency([], [s1, s2])
        assert any(f.rule == "C1" for f in report.corrections)
        # 同来源(评审 P0-14):单文件内多段引用不算跨来源不一致
        s3 = Statement(id="st.3", kind="rule",
                       slots={"about": "cap:c.x",
                              "violation": "outcome:u.last"})
        s3._source = "prd.md"
        report_same = validate_consistency([], [s1, s3])
        assert not [f for f in report_same.corrections if f.rule == "C1"]

    def test_c1_subset_is_compatible(self) -> None:
        """修订十二不冲突口径:一来源是另一来源的子集 = 部分描述,
        不报(PRD 只写主干,接口文档列全 → 有公共 cap 即兼容)。"""
        s1 = Statement(id="st.1", kind="rule",
                       slots={"about": "cap:a.down",
                              "violation": "outcome:u.last"})
        s1._source = "prd.md"
        s2 = Statement(id="st.2", kind="outcome",
                       slots={"cap": "cap:a.down", "outcome": "outcome:u.last"})
        s3 = Statement(id="st.3", kind="outcome",
                       slots={"cap": "cap:b.del", "outcome": "outcome:u.last"})
        s2._source = s3._source = "api.md"   # 同来源合并为 {a.down, b.del}
        report = validate_consistency([], [s1, s2, s3])
        assert not [f for f in report.corrections if f.rule == "C1"]

    def test_c1_no_consensus_across_three_sources_reports(self) -> None:
        """修订十二口径钉死(M3 拍板):判「全部来源的交集为空」——三份
        文档两两有交集、但没有一个 cap 是三方都认可的({del,demote}/
        {demote,login}/{login,del})时**报**。没有共同事实 = 无一致归属,
        交矫正裁定;any-pairwise-disjoint 口径会漏掉这种环形分歧。"""
        def rule(sid, cap, src):
            s = Statement(id=sid, kind="rule",
                          slots={"about": cap, "violation": "outcome:u.last"})
            s._source = src
            return s
        r = validate_consistency([], [
            rule("s1", "cap:del", "prd.md"),
            rule("s2", "cap:demote", "api.md"),
            rule("s3", "cap:login", "state.md"),
        ])
        assert any(f.rule == "C1" for f in r.corrections)

    def test_c3_edge_conflict_and_complement(self) -> None:
        """修订十二不冲突口径(边级):同一 from 去向不相交才报;
        互补边(a→b 与 b→c)= 部分描述,不报。"""
        def tr(sid, f, t, src):
            s = Statement(id=sid, kind="transition",
                          slots={"cap": "cap:o.x", "from": f, "to": t})
            s._source = src
            return s
        # 互补:doc1 a→b;doc2 b→c(旧集合口径会误报,边级不报)
        ok = validate_consistency([], [
            tr("t1", "value:s.p.a", "value:s.p.b", "state1.md"),
            tr("t2", "value:s.p.b", "value:s.p.c", "state2.md"),
        ])
        assert not [f for f in ok.corrections if f.rule == "C3"]
        # 部分描述:同一 from a,doc1 去向 {b},doc2 去向 {b,c}(分支)→ 不报
        ok2 = validate_consistency([], [
            tr("t3", "value:s.p.a", "value:s.p.b", "state1.md"),
            tr("t4", "value:s.p.a", "value:s.p.b", "state2.md"),
            tr("t5", "value:s.p.a", "value:s.p.c", "state2.md"),
        ])
        assert not [f for f in ok2.corrections if f.rule == "C3"]
        # 冲突:同一 from a,doc1 → b,doc2 → c(无公共去向)→ 报
        bad = validate_consistency([], [
            tr("t6", "value:s.p.a", "value:s.p.b", "state1.md"),
            tr("t7", "value:s.p.a", "value:s.p.c", "state2.md"),
        ])
        assert any(f.rule == "C3" for f in bad.corrections)


class TestCheckStageF3:
    """评审第三轮:check 阶段的树级 F3(与 release 闸门同口径)——
    跨文件重复的接口 id / 路由键 / 片段 id 在入库闸门即拦,
    此前只有交付物 id 在 check 查、其余要到发版。"""

    EP_MD = ("---\nid: {fid}\ntype: endpoints\nsystem: x\n---\n"
             "```gimbal:endpoint\nreview: reviewed\n"
             "id: {eid}\nsystem: x\nservice: svc\nname: n\n"
             "binding:\n  protocol: http\n  method: GET\n  path: {path}\n"
             "responses:\n  '200': {{}}\n```\n")
    ST_MD = ("---\nid: {fid}\ntype: prd\nsystem: x\n---\n"
             "```gimbal:statement\nreview: reviewed\n"
             "id: st.dup\nkind: rule\nslots: {{about: cap:a.b}}\n"
             "anchor: 'A1'\n```\n原文\n")

    def _tree(self, tmp_path, files: list[tuple[str, str, str, str]]):
        root = tmp_path / "systems" / "x"
        (root / "endpoints").mkdir(parents=True, exist_ok=True)
        (root / "deliverables").mkdir(parents=True, exist_ok=True)
        from gimbal_plate.dialect.validation import validate_system_tree
        for fname, fid, eid, path in files:
            target = root / fname
            if Path(fname).name.startswith("prd"):
                target.write_text(self.ST_MD.format(fid=fid), encoding="utf-8")
            else:
                target.write_text(
                    self.EP_MD.format(fid=fid, eid=eid, path=path),
                    encoding="utf-8")
        return validate_system_tree(root, types=load_types())

    def test_duplicate_endpoint_id_blocked_at_check(self, tmp_path):
        rep = self._tree(tmp_path, [
            ("endpoints/a.md", "x.a", "x.ep", "/a"),
            ("endpoints/b.md", "x.b", "x.ep", "/b"),
        ])
        assert any(f.rule == "F3" and "接口 id" in f.message for f in rep.blocking)

    def test_duplicate_route_key_blocked_at_check(self, tmp_path):
        rep = self._tree(tmp_path, [
            ("endpoints/a.md", "x.a", "x.ep1", "/same"),
            ("endpoints/b.md", "x.b", "x.ep2", "/same"),
        ])
        assert any(f.rule == "F3" and "路由键" in f.message for f in rep.blocking)

    def test_duplicate_statement_id_blocked_at_check(self, tmp_path):
        rep = self._tree(tmp_path, [
            ("endpoints/a.md", "x.a", "x.ep", "/a"),
            ("deliverables/prd1.md", "x.p1", "", ""),
            ("deliverables/prd2.md", "x.p2", "", ""),
        ])
        assert any(f.rule == "F3" and "片段 id" in f.message for f in rep.blocking)

    def test_clean_tree_no_f3(self, tmp_path):
        rep = self._tree(tmp_path, [("endpoints/a.md", "x.a", "x.ep", "/a")])
        assert not [f for f in rep.blocking if f.rule == "F3"]

    def test_c1_source_from_parser(self) -> None:
        """评审 R1 回归:_source 由解析器在生产路径记录(不再手工设置),
        两个真实文件(prd + endpoints)各挂同一 outcome 到不同 cap →
        release 级 C 闸门必须阻塞。"""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        (tmp / "systems" / "x").mkdir(parents=True)
        (tmp / "systems" / "x" / "dictionary").mkdir()
        (tmp / "systems" / "x" / "dictionary" / "user.md").write_text(
            "---\nid: x.dict.user\ntype: dictionary\nsystem: x\n---\n# U\n\n"
            "```gimbal:term\n"
            "- id: entity:user\n  label: 用户\n"
            "- id: cap:user.update\n  label: 更新用户\n"
            "- id: cap:user.delete\n  label: 删除用户\n"
            "- id: outcome:user.last_admin\n  label: 最后管理员\n"
            "```\n",
            encoding="utf-8")
        (tmp / "systems" / "x" / "deliverables").mkdir()
        (tmp / "systems" / "x" / "deliverables" / "prd.md").write_text(
            "---\nid: x.prd.r\ntype: prd\nsystem: x\n---\n# R\n\n"
            "```gimbal:statement\nreview: reviewed\n"
            "id: st.prd.1\nkind: rule\n"
            "slots: {about: cap:user.update, violation: outcome:user.last_admin}\n"
            "anchor: 'A1'\n```\n不能降级最后一个管理员。\n",
            encoding="utf-8")
        (tmp / "systems" / "x" / "endpoints").mkdir()
        (tmp / "systems" / "x" / "endpoints" / "user.md").write_text(
            "---\nid: x.ep.u\ntype: endpoints\nsystem: x\n---\n# U\n\n"
            "```gimbal:statement\nreview: reviewed\n"
            "id: st.ep.1\nkind: outcome\n"
            "slots: {cap: cap:user.delete, outcome: outcome:user.last_admin}\n"
            "anchor: 'A2'\n```\n删除最后一个管理员被拒绝。\n",
            encoding="utf-8")
        r = release_system(tmp / "systems" / "x",
                           artifacts_root=tmp / "arts", signed_by="t")
        assert not r.success
        assert "C 类一致性未处理" in r.message, r.message
        assert any(f.rule == "C1" for f in r.report.corrections)


def _deliverable_with_statement(st: Statement):
    from gimbal_plate.dialect.parser import Block, Deliverable, Prose
    from gimbal_plate.dialect import Frontmatter
    return Deliverable(
        frontmatter=Frontmatter(type="user_story"),
        nodes=[Block(type="statement", payload=st)],
        source="<test>",
    )


class TestRelease:
    def test_freeze_and_content_addressing(self, tmp_path: Path) -> None:
        systems = tmp_path / "systems"
        (systems / "fin" / "endpoints").mkdir(parents=True)
        ep_md = systems / "fin" / "endpoints" / "fin.a.b.md"
        ep_md.write_text(
            "---\nid: fin.a.b\ntype: endpoints\nsystem: fin\n---\n"
            "# b\n\n```gimbal:endpoint\nreview: reviewed\n"
            "id: fin.a.b\nsystem: fin\nservice: fin-service\nname: b\n"
            "binding:\n  protocol: http\n  method: GET\n  path: /b\n"
            "responses:\n  '200': {}\n```\n",
            encoding="utf-8")
        artifacts = tmp_path / "artifacts"

        r1 = release_system(systems / "fin", artifacts_root=artifacts,
                            signed_by="tester")
        assert r1.success, r1.message
        assert r1.release_id.endswith(".1")
        assert r1.manifest["summary"]["endpoints"] == 1
        obj_count = len(list((artifacts / "objects").glob("*.json")))
        assert obj_count == 1
        first_hash = r1.manifest["objects"][0]["hash"]
        # 对象内容与 hash 自洽
        obj = json.loads((artifacts / "objects" / f"{first_hash}.json").read_text(encoding="utf-8"))
        assert obj["kind"] == "endpoint" and obj["id"] == "fin.a.b"

        # 二次冻结:同内容 → 池不增长,manifest hash 全同,序号 +1
        r2 = release_system(systems / "fin", artifacts_root=artifacts,
                            signed_by="t2")
        assert r2.success and r2.release_id.endswith(".2")
        assert len(list((artifacts / "objects").glob("*.json"))) == 1
        assert r2.manifest["objects"][0]["hash"] == first_hash

        # 内容变更 → 新 hash,旧对象保留(只追加)
        ep_md.write_text(ep_md.read_text(encoding="utf-8").replace("name: b", "name: b2"), encoding="utf-8")
        r3 = release_system(systems / "fin", artifacts_root=artifacts,
                            signed_by="t3")
        assert r3.success
        assert r3.manifest["objects"][0]["hash"] != first_hash
        assert len(list((artifacts / "objects").glob("*.json"))) == 2

    def test_draft_blocks_skipped_not_blocking(self, tmp_path: Path) -> None:
        systems = tmp_path / "systems"
        (systems / "fin" / "endpoints").mkdir(parents=True)
        (systems / "fin" / "endpoints" / "fin.a.c.md").write_text(
            "---\nid: fin.a.c\ntype: endpoints\nsystem: fin\n---\n"
            "```gimbal:endpoint\nid: fin.a.c\nsystem: fin\nservice: fin-service\n"
            "name: c\nbinding:\n  protocol: http\n  method: GET\n  path: /c\n"
            "responses:\n  '200': {}\n```\n",  # 无 review → draft(缺省)
            encoding="utf-8")
        r = release_system(systems / "fin", artifacts_root=tmp_path / "art",
                           signed_by="t")
        # 8v:draft 块不进 release,但不阻塞(与词条同口径,修订九)
        assert r.success
        assert r.manifest["summary"]["endpoints"] == 0
        assert r.manifest["summary"]["draft_skipped_endpoints"] == 1

    def test_closure_blocks_on_referenced_unfrozen_term(self, tmp_path: Path) -> None:
        systems = tmp_path / "systems"
        (systems / "fin" / "endpoints").mkdir(parents=True)
        # reviewed 端点引用 draft 词条(无该词条文件 → 引用闭包应阻塞在 S2;
        # 有词条但 draft → 闭包阻塞)
        (systems / "fin" / "dictionary").mkdir()
        (systems / "fin" / "dictionary" / "d.md").write_text(
            "---\ntype: dictionary\nsystem: fin\n---\n"
            "```gimbal:term\n- id: entity:a\n  label: A\n"
            "- id: cap:a.b\n  label: B\n```\n",  # draft(缺省)
            encoding="utf-8")
        (systems / "fin" / "endpoints" / "fin.a.d.md").write_text(
            "---\nid: fin.a.d\ntype: endpoints\nsystem: fin\n---\n"
            "```gimbal:endpoint\nreview: reviewed\n"
            "id: fin.a.d\nsystem: fin\nservice: fin-service\nname: d\n"
            "capability: cap:a.b\n"
            "binding:\n  protocol: http\n  method: GET\n  path: /d\n"
            "responses:\n  '200': {}\n```\n",
            encoding="utf-8")
        r = release_system(systems / "fin", artifacts_root=tmp_path / "art",
                           signed_by="t")
        assert not r.success
        assert "引用闭包" in r.message

    def test_closure_starts_from_all_reviewed_terms(self, tmp_path: Path) -> None:
        """评审 R4 回归:闭包起点 = 全部 reviewed 词条(非只被块引用的)。
        reviewed 词条未被任何块引用,但自身 refers 到 draft 词条 / 父节点
        draft → 仍须阻塞。"""
        systems = tmp_path / "systems"
        (systems / "fin" / "dictionary").mkdir(parents=True)
        (systems / "fin" / "dictionary" / "d.md").write_text(
            "---\ntype: dictionary\nsystem: fin\n---\n"
            # attr:a.b reviewed,refers 到 draft 的 attr:a.c;父 entity:a 也 draft
            "```gimbal:term\n"
            "- id: attr:a.b\n  label: B\n  refers: attr:a.c\n  review: reviewed\n"
            "```\n"
            "```gimbal:term\n"
            "- id: entity:a\n  label: A\n"
            "- id: attr:a.c\n  label: C\n"
            "```\n",
            encoding="utf-8")
        # 一个 reviewed 端点保证 release 有可冻结内容(不带词条引用)
        (systems / "fin" / "endpoints").mkdir()
        (systems / "fin" / "endpoints" / "fin.a.f.md").write_text(
            "---\nid: fin.a.f\ntype: endpoints\nsystem: fin\n---\n"
            "```gimbal:endpoint\nreview: reviewed\n"
            "id: fin.a.f\nsystem: fin\nservice: fin-service\nname: f\n"
            "binding:\n  protocol: http\n  method: GET\n  path: /f\n"
            "responses:\n  '200': {}\n```\n",
            encoding="utf-8")
        r = release_system(systems / "fin", artifacts_root=tmp_path / "art",
                           signed_by="t")
        assert not r.success
        assert "引用闭包" in r.message

    def test_f4_checklist_threshold(self, tmp_path: Path) -> None:
        systems = tmp_path / "systems"
        (systems / "fin" / "endpoints").mkdir(parents=True)
        (systems / "fin" / "endpoints" / "fin.a.e.md").write_text(
            "---\nid: fin.a.e\ntype: endpoints\nsystem: fin\n---\n"
            "```gimbal:endpoint\nreview: reviewed\n"
            "id: fin.a.e\nsystem: fin\nservice: fin-service\nname: e\n"
            "binding:\n  protocol: http\n  method: GET\n  path: /e\n"
            "responses:\n  '200': {}\n```\n",
            encoding="utf-8")
        r = release_system(systems / "fin", artifacts_root=tmp_path / "a",
                           signed_by="t", checklist={"endpoints_with_capability": 1})
        assert not r.success and "F4" in r.message or "交付件清单" in r.message

    def test_call_projection_shape(self) -> None:
        ep = _mk_ep()
        proj = _call_projection(ep)
        assert proj == {
            "kind": "call", "protocol": "http", "service": "svc",
            "timeout": 30.0, "method": "GET", "path": "/ping", "headers": {},
        }


class TestGaps:
    def test_gap_items_counts(self) -> None:
        eps = [
            _mk_ep(),
            _mk_ep(id="t.svc.two", binding={"protocol": "http", "method": "POST",
                                            "path": "/two"},
                   capability="cap:t.run", responses={"200": {}, "409": {}}),
        ]
        sts = [Statement(id="st.s", kind="step",
                         slots={"cap": "cap:t.run", "order": 1})]
        items = gap_items(eps, sts, {})
        assert items["endpoints_total"] == 2
        assert items["endpoints_with_capability"] == 1
        assert items["core_business_without_story"] == 0  # cap:t.run 有 step

    def test_gaps_http_action(self, http_client) -> None:
        resp = http_client.post("/api/systems/fin/system/action/gaps")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert items["endpoints_total"] == 23
        assert items["endpoints_with_capability"] == 0  # 语义标注属批次 E

    def test_check_http_action_ok(self, http_client) -> None:
        resp = http_client.post("/api/systems/fin/system/action/check")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["ok"] is True
        assert body["total"] >= 0

    def test_release_http_action_writes_manifest(self, http_client, tmp_path,
                                                 monkeypatch) -> None:
        # 指到临时 artifacts,不污染仓库。patch 目标必须是**包属性**
        # gimbal_plate.release.release_system(routes_grammar 的函数内
        # `from gimbal_plate.release import release_system` 按包属性解析;
        # 此前 patch 在子模块 gimbal_plate.release.release 上,路由拿到
        # 的仍是原函数 → 测试把 manifest 写进了仓库 plate_artifacts/,
        # 评审降级清单第 15 项)。
        import gimbal_plate.release as release_pkg
        real = release_pkg.release_system
        monkeypatch.setattr(
            release_pkg, "release_system",
            lambda root, **kw: real(
                root, **{**kw, "artifacts_root": tmp_path / "art"}),
        )
        resp = http_client.post("/api/systems/fin/system/action/release",
                                json={"signed_by": "tester"})
        assert resp.status_code == 200
        item = resp.json()["data"]["item"]
        assert item["success"] is True
        assert item["summary"]["endpoints"] == 23

    def test_release_http_action_requires_system(self, http_client) -> None:
        """评审 R2:全局路由(无系统名)不得把 systems/ 整树当一个系统冻结。"""
        resp = http_client.post("/api/system/action/release",
                                json={"signed_by": "tester"})
        assert resp.status_code == 400
        assert "system required" in resp.json()["error"]["message"]
