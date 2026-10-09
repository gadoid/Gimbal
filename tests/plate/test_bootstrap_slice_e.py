"""批次 E 自举切片:platform「管理员管理成员」原生内容过全链。

内容(全部 reviewed,信封在块上):
- deliverables/prd-user-management.md   define/rule/outcome 片段
- deliverables/story-admin-manages-members.md  user_story(5 step)
- dictionary/user.md                    10 词条(entity/attr/value/cap/outcome)
- 四个 users 接口挂 capability(语义标注)

验证链:check(闸门)→ gaps 收敛 → release(含词条闭包)→ 词条图反查 →
L6 起点(cap 有 story 覆盖)。
"""
from __future__ import annotations

import json
from pathlib import Path

from gimbal_plate.cli import _REPO, main
from gimbal_plate.dialect import EndpointSpec, Statement, Term, parse_markdown

PLAT = _REPO / "systems" / "platform"


def _tree():
    endpoints, statements, terms = [], [], {}
    for md in sorted(PLAT.rglob("*.md")):
        d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
        for b in d.blocks():
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    endpoints.append(m)
                elif isinstance(m, Statement):
                    statements.append(m)
                elif isinstance(m, Term):
                    terms[m.id] = m
    return endpoints, statements, terms


class TestAuthoredContent:
    def test_prd_statements_present(self) -> None:
        _, statements, _ = _tree()
        by_id = {s.id: s for s in statements}
        assert by_id["st.user-mgmt.last-admin"].kind == "rule"
        assert by_id["st.user-mgmt.last-admin"].slots["violation"] == \
            "outcome:user.last_admin"
        assert by_id["st.user-mgmt.disable-last-admin"].kind == "outcome"
        assert by_id["st.user-mgmt.disable-last-admin"].slots["when"] == \
            ["value:user.role.admin"]
        # 片段原文派生
        assert "不能降级最后一个管理员" in by_id["st.user-mgmt.last-admin"].text

    def test_user_story_five_steps_with_branch(self) -> None:
        # P2 内容交付(prd-suite-and-sharing + 4 个故事)加入后,按来源
        # 文件过滤到本切片的 user-mgmt 故事(否则计数被新故事污染)。
        _, statements, _ = _tree()
        steps = sorted(
            (s for s in statements
             if s.kind == "step"
             and getattr(s, "_source", "").endswith(
                 "story-admin-manages-members.md")),
            key=lambda s: s.slots["order"])
        assert [s.slots["order"] for s in steps] == [1, 2, 3, 4, 5]
        assert steps[3].slots["branch_on"] == "outcome:user.last_admin"

    def test_dictionary_kinds_complete(self) -> None:
        _, _, terms = _tree()
        kinds = {t.id.split(":")[0] for t in terms.values()}
        assert kinds == {"entity", "attr", "value", "cap", "outcome"}
        assert terms["entity:user"].aliases == ["用户", "账号"]

    def test_capability_annotations(self) -> None:
        endpoints, _, _ = _tree()
        caps = {e.id: e.capability for e in endpoints if e.capability}
        assert caps == {
            "platform.users.post_root": "cap:user.create",
            "platform.users.patch_by_user_id": "cap:user.update",
            "platform.users.delete_by_user_id": "cap:user.disable",
            "platform.users.post_by_user_id_reset_password":
                "cap:user.reset_password",
        }


class TestGates:
    def test_check_passes_ingress_gate(self) -> None:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["check", "platform", "--json"])
        assert rc == 0
        assert json.loads(buf.getvalue())["ok"] is True

    def test_gaps_converged_for_slice(self) -> None:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["gaps", "platform", "--json"])
        items = json.loads(buf.getvalue())["items"]
        # 四个管理动作全部有 story 覆盖(L6 起点)
        assert items["core_business_without_story"] == 0
        # 切片内 4 接口挂 capability(全量 126 收敛属后续标注,非本切片验收)
        assert items["endpoints_with_capability"] == 4

    def test_release_freezes_with_term_closure(self, tmp_path) -> None:
        from gimbal_plate.release.release import release_system

        r = release_system(PLAT, artifacts_root=tmp_path / "art",
                           signed_by="slice-tester")
        assert r.success, r.message
        assert r.manifest["summary"]["endpoints"] == 126
        # P2 内容交付后 statements 增多;原切片 10 条作为下限断言
        assert r.manifest["summary"]["statements"] >= 10
        # 11 = 原切片 10 + 三级角色更名(0011)补的 value:user.role.user
        # (fb47a066 更名字典加词条但漏改本期望——拉取侧回弹,此处补齐)
        assert r.manifest["summary"]["terms"] >= 11
        # call 投影含 capability 关联的四个管理动作
        assert "platform.users.post_root" in r.manifest["call_projections"]

    def test_term_reference_backlink(self) -> None:
        """词条反查:outcome:user.last_admin 被 rule 与 outcome 双向引用。"""
        _, statements, _ = _tree()
        refs = [s.id for s in statements
                if "outcome:user.last_admin" in
                (str(s.slots.get("violation")) + str(s.slots.get("outcome"))
                 + str(s.slots.get("branch_on")))]
        assert set(refs) == {"st.user-mgmt.last-admin",
                             "st.user-mgmt.disable-last-admin",
                             "st.story.admin.4"}
