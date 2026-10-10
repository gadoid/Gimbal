"""S1.5a 校验收口(2026-10-10):plate-s1-review 第 4 节清单。

覆盖:
- check --all(systems 根全量遍历 + 不合规目录名点名);
- 校验口子:responses 空、列表块 service 继承、YAML 合并键 / 复合键、
  S4(anchor 语法 + spec_path 解析)、T5(alias vs label)、T3/T6(common
  目标不误阻塞);
- F3 finding 行号(解析期记 _line,重复定位非 0 行)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.dialect.models import EndpointSpec, Term
from gimbal_plate.dialect.parser import DialectError, parse_markdown, strict_yaml_load
from gimbal_plate.dialect.validation import (
    load_types,
    validate_system_tree,
    validate_terms,
)


def _mk_system(tmp_path: Path, files: dict[str, str], name: str = "t") -> Path:
    root = tmp_path / "systems" / name
    root.mkdir(parents=True)
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


# ── responses 空(S1.5a:此前静默通过)────────────────────────────


def test_empty_responses_rejected() -> None:
    with pytest.raises(Exception, match="responses 不得为空"):
        EndpointSpec.model_validate(dict(
            id="t.svc.ping", system="t", service="svc", name="ping",
            binding={"protocol": "http", "method": "GET", "path": "/ping"},
            responses={},
        ))


# ── 列表块继承 frontmatter.service(此前仅单块继承)──────────────


def _ep_file(body: str, fm_service: str | None = None) -> str:
    fm = f"---\ntype: endpoints\nsystem: t\nservice: {fm_service}\n---\n" \
        if fm_service else "---\ntype: endpoints\nsystem: t\n---\n"
    return fm + body + "\n"


SINGLE_EP = """```gimbal:endpoint
id: t.svc.one
system: t
service: svc
name: one
binding: {protocol: http, method: GET, path: /one}
responses: {"200": {}}
```"""

LIST_EP = """```gimbal:endpoint
- id: t.svc.a
  system: t
  name: a
  binding: {protocol: http, method: GET, path: /a}
  responses: {"200": {}}
- id: t.svc.b
  system: t
  name: b
  binding: {protocol: http, method: GET, path: /b}
  responses: {"200": {}}
```"""


def test_list_block_inherits_frontmatter_service(tmp_path: Path) -> None:
    md = tmp_path / "list.md"
    md.write_text(_ep_file(LIST_EP, fm_service="shared"),
                  encoding="utf-8")
    d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
    eps = [m for b in d.blocks() for m in b.models()
           if isinstance(m, EndpointSpec)]
    assert len(eps) == 2
    assert all(ep.service == "shared" for ep in eps), \
        "列表块条目应继承 frontmatter.service(单块继承、列表块漏)"


def test_list_block_explicit_service_not_overridden(tmp_path: Path) -> None:
    body = """```gimbal:endpoint
- id: t.svc.a
  system: t
  service: own
  name: a
  binding: {protocol: http, method: GET, path: /a}
  responses: {"200": {}}
```"""
    md = tmp_path / "one.md"
    md.write_text(_ep_file(body, fm_service="shared"), encoding="utf-8")
    d = parse_markdown(md.read_text(encoding="utf-8"), source=str(md))
    ep = next(m for b in d.blocks() for m in b.models()
              if isinstance(m, EndpointSpec))
    assert ep.service == "own", "显式 service 不被继承覆盖"


# ── YAML 合并键 / 复合键(此前静默字面量化 / 裸 TypeError)──────


def test_merge_key_rejected() -> None:
    with pytest.raises(DialectError, match="合并键"):
        strict_yaml_load("base: &b {x: 1}\nitem:\n  <<: *b\n  y: 2",
                         source="t.md", line=1)


def test_complex_key_rejected() -> None:
    with pytest.raises(DialectError):
        strict_yaml_load("? [a, b]\n: v", source="t.md", line=1)


# ── T5:alias 与他词条 label 冲突(S1.5a 补齐口径)───────────────


def _term(**over) -> Term:
    base = dict(id="attr:user.name", label="用户名", status="active")
    base.update(over)
    return Term.model_validate(base)


def test_t5_alias_vs_foreign_label() -> None:
    rep = validate_terms([
        _term(id="attr:user.name", label="用户名"),
        _term(id="attr:user.age", label="年龄", aliases=["用户名"]),
    ], system_id="t")
    hits = [f for f in rep.findings if f.rule == "T5"]
    assert hits and "label 冲突" in hits[0].message


def test_t5_alias_vs_own_label_not_flagged() -> None:
    rep = validate_terms([
        _term(id="attr:user.name", label="用户名", aliases=["用户名"]),
    ], system_id="t")
    assert not [f for f in rep.findings if f.rule == "T5"]


# ── T3/T6:common 目标不误阻塞(S1.5a)───────────────────────────


def test_t3_t6_common_target_not_flagged() -> None:
    common = {"attr:shared.token"}
    rep = validate_terms([
        _term(id="attr:user.name", label="用户名",
              replaced_by="attr:shared.token"),
        _term(id="attr:user.age", label="年龄", refers="attr:shared.token"),
    ], system_id="t", common_ids=common)
    blocks = [f for f in rep.findings if f.rule in ("T3", "T6")]
    assert not blocks, f"common 目标不应误报: {[f.message for f in blocks]}"


def test_t3_local_target_must_exist() -> None:
    rep = validate_terms([
        _term(id="attr:user.name", label="用户名",
              replaced_by="attr:user.gone"),
    ], system_id="t")
    assert any(f.rule == "T3" and "不存在" in f.message
               for f in rep.findings)


def test_t6_local_target_must_be_active() -> None:
    rep = validate_terms([
        _term(id="attr:user.age", label="年龄",
              refers="attr:user.name"),
        _term(id="attr:user.name", label="用户名", status="deprecated"),
    ], system_id="t")
    assert any(f.rule == "T6" for f in rep.findings)


# ── S4:anchor 语法 + spec_path 解析(S1.5a 补实现)──────────────


def _notes_system(tmp_path: Path, anchor: str) -> object:
    files = {
        "endpoints/ep.md": _ep_file(SINGLE_EP),
        "endpoints/notes.md": (
            "---\ntype: endpoints\nsystem: t\n---\n"
            "```gimbal:statement\n"
            "id: st.note\nkind: note\n"
            f"anchor: {json.dumps(anchor, ensure_ascii=False)}\n"
            "```\n正文\n"),
    }
    return validate_system_tree(_mk_system(tmp_path, files),
                                types=load_types())


def test_s4_bad_spec_path_syntax_warns(tmp_path: Path) -> None:
    rep = _notes_system(tmp_path, "无空格无路径")
    hits = [f for f in rep.findings if f.rule == "S4"]
    assert hits and "锚点语法" in hits[0].message


def test_s4_spec_path_unknown_endpoint_warns(tmp_path: Path) -> None:
    rep = _notes_system(tmp_path, "t.svc.gone $.data.x")
    hits = [f for f in rep.findings if f.rule == "S4"]
    assert hits and "t.svc.gone" in hits[0].message


def test_s4_spec_path_unknown_outcome_warns(tmp_path: Path) -> None:
    rep = _notes_system(tmp_path, "t.svc.one $.data.x@404")
    hits = [f for f in rep.findings if f.rule == "S4"]
    assert hits and "404" in hits[0].message


def test_s4_spec_path_valid_no_warning(tmp_path: Path) -> None:
    rep = _notes_system(tmp_path, "t.svc.one $.data.order_id@200")
    assert not [f for f in rep.findings if f.rule == "S4"]


# ── F3 行号(S1.5a:此前恒为 0)──────────────────────────────────


def test_f3_duplicate_has_line_number(tmp_path: Path) -> None:
    ep = """---
type: endpoints
system: t
---
```gimbal:endpoint
id: t.svc.dup
system: t
service: svc
name: dup
binding: {protocol: http, method: GET, path: /dup}
responses: {"200": {}}
```
"""
    files = {"endpoints/a.md": ep, "endpoints/b.md": ep}
    rep = validate_system_tree(_mk_system(tmp_path, files), types=load_types())
    dup = [f for f in rep.findings
           if f.rule == "F3" and "重复" in f.message]
    assert dup, "跨文件重复接口 id 应报 F3"
    assert dup[0].line and dup[0].line > 0, \
        f"F3 finding 应带块行号(此前恒 0): {dup[0].line}"


# ── check --all(CI 口径:遍历 systems 根,不合规目录名报错)─────


class TestCheckAll:
    def test_all_traverses_every_system(self, tmp_path, monkeypatch, capsys):
        import gimbal_plate.cli as cli
        monkeypatch.setattr(cli, "_REPO", tmp_path)
        sys_root = tmp_path / "systems"
        (sys_root / "common" / "endpoints").mkdir(parents=True)
        (sys_root / "finx" / "endpoints").mkdir(parents=True)
        (sys_root / "common" / "endpoints" / "terms.md").write_text(
            "---\ntype: dictionary\nsystem: common\n---\n"
            "```gimbal:term\nid: entity:shared\nlabel: 共享\n```\n"
            "```gimbal:term\nid: attr:shared.token\nlabel: 令牌\n"
            "```\n", encoding="utf-8")
        (sys_root / "finx" / "endpoints" / "ep.md").write_text(
            "---\ntype: endpoints\nsystem: finx\n---\n"
            "```gimbal:endpoint\n"
            "id: finx.svc.one\nsystem: finx\nservice: svc\nname: one\n"
            "binding: {protocol: http, method: GET, path: /one}\n"
            'responses: {"200": {}}\n'
            "```\n", encoding="utf-8")
        (sys_root / "bad.v2").mkdir()  # 不合规名:--all 应点名
        rc = cli.main(["check", "--all", "--json"])
        assert rc == 0
        out = capsys.readouterr()
        assert "bad.v2" in out.err and "不合规" in out.err

    def test_all_aggregates_blocking(self, tmp_path, monkeypatch):
        import gimbal_plate.cli as cli
        monkeypatch.setattr(cli, "_REPO", tmp_path)
        sys_root = tmp_path / "systems"
        (sys_root / "a" / "endpoints").mkdir(parents=True)
        (sys_root / "b" / "endpoints").mkdir(parents=True)
        broken = ("---\ntype: nope\n---\n"
                  "```gimbal:term\nid: entity:x\nlabel: X\n```\n")
        (sys_root / "a" / "endpoints" / "x.md").write_text(broken, encoding="utf-8")
        (sys_root / "b" / "endpoints" / "x.md").write_text(broken, encoding="utf-8")
        rc = cli.main(["check", "--all", "--json"])
        assert rc == 1, "任一系统阻塞则整体红"
