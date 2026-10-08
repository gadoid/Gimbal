"""批次 D 测试：plate CLI + G1 自描述 + G3 词条检索 + review 置位。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.cli import main


class TestCliCheck:
    def test_check_fin_ok(self, capsys) -> None:
        assert main(["check", "fin", "--json"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is True

    def test_check_stdin_bad_type(self, capsys) -> None:
        import sys
        from io import StringIO
        old, sys.stdin = sys.stdin, StringIO(
            "---\ntype: nope\n---\n```gimbal:term\nid: entity:x\nlabel: X\n```\n")
        try:
            assert main(["check", "--stdin", "--json"]) == 1
            out = json.loads(capsys.readouterr().out)
            assert any(f["rule"] == "F1" for f in out["blocking"])
        finally:
            sys.stdin = old


class TestCliGapsAndTerm:
    def test_gaps_json(self, capsys) -> None:
        assert main(["gaps", "fin", "--json"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["items"]["endpoints_total"] == 23

    def test_term_search_common_and_local(self, capsys, tmp_path,
                                          monkeypatch) -> None:
        # 在**临时仓库根**的 fin 词典加词条 → 检索命中(label+alias+相似度)。
        # 不写真源 systems/(评审降级清单第 15 项:测试不得往仓库写东西)。
        from gimbal_plate import cli
        (tmp_path / "systems" / "fin" / "dictionary").mkdir(parents=True)
        monkeypatch.setattr(cli, "_REPO", tmp_path)
        (tmp_path / "systems" / "fin" / "dictionary" / "t.md").write_text(
            "---\ntype: dictionary\nsystem: fin\n---\n"
            "```gimbal:term\n- id: entity:order\n  label: 订单\n  aliases: [委托单]\n"
            "- id: cap:order.create\n  label: 创建订单\n```\n",
            encoding="utf-8")
        assert main(["term", "search", "委托单", "--system", "fin",
                     "--json"]) == 0
        hits = json.loads(capsys.readouterr().out)["hits"]
        assert any(h["id"] == "entity:order" and "alias" in "/".join(
            h["matched_by"]) for h in hits)
        assert main(["term", "search", "订单", "--system", "fin",
                     "--json"]) == 0
        hits2 = json.loads(capsys.readouterr().out)["hits"]
        assert any(h["id"] == "cap:order.create" for h in hits2)


class TestCliNewAndReview:
    def test_new_and_review_roundtrip(self, capsys, tmp_path, monkeypatch) -> None:
        # 临时仓库根(评审降级清单第 15 项:此前写到真源 systems/fin/ 下,
        # 失败中断即残留);types 仍指向真源模板。
        from gimbal_plate import cli
        (tmp_path / "systems" / "fin").mkdir(parents=True)
        monkeypatch.setattr(cli, "_REPO", tmp_path)
        target = tmp_path / "systems" / "fin" / "deliverables" / "_cli_new_prd.md"
        assert main(["new", "prd", "--system", "fin", "--id",
                     "_cli_new_prd"]) == 0
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert "type: prd" in text and "gimbal:statement" in text
        # review 置位 → 规范形回写带 review: reviewed
        assert main(["review", "fin.prd._cli_new_prd"]) == 0
        text2 = target.read_text(encoding="utf-8")
        assert "review: reviewed" in text2
        # 校验:骨架 statement 的 slots 为注释占位 → S1 红(引擎拦手写骨架)
        assert main(["check", "fin", "--json"]) == 1


class TestG1SelfDescribe:
    def test_type_dim_via_http(self, http_client) -> None:
        resp = http_client.get("/api/type")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert {t["id"] for t in items} >= {"prd", "user_story", "endpoints"}

    def test_full_schema_view(self) -> None:
        from gimbal_plate.dialect.selfdescribe_view import TypeCatalogIndex
        schema = TypeCatalogIndex().full_schema()
        assert set(schema["blocks"]) == {
            "endpoint", "statement", "term", "frontmatter"}
        assert schema["statement_kind_slots"]["rule"]["required"] == ["about"]
        assert schema["canonical_form"]["exclude_defaults"] is True
