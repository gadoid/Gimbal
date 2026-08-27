"""scan_auth_aliases — 后端版 tpl-refs(语义对齐 frontend/src/utils/tpl-refs.ts)。"""
from app.services.auth_ref_scan import scan_auth_aliases


def test_headers_reference() -> None:
    steps = [{"api": {"headers": {"Authorization": "${auth.qa1.token}"}}}]
    assert scan_auth_aliases(steps) == ["qa1"]


def test_nested_body_and_list() -> None:
    steps = [{
        "api": {"path": "/x"},
        "request": {"body": {"creds": [{"u": "${auth.qa1.user}", "p": "${auth.qa1.pass}"}]}},
        "strategy": [{"message": "fail as ${auth.qa2.name}"}],
    }]
    assert scan_auth_aliases(steps) == ["qa1", "qa2"]


def test_dedup_keeps_first_seen_order() -> None:
    steps = [
        {"api": {"headers": {"a": "${auth.b.token}"}}},
        {"api": {"headers": {"b": "${auth.a.token}"}}},
        {"api": {"headers": {"c": "${auth.b.token}"}}},
    ]
    assert scan_auth_aliases(steps) == ["b", "a"]


def test_fieldless_reference_counts() -> None:
    steps = [{"api": {"headers": {"x": "${auth.qa1}"}}}]
    assert scan_auth_aliases(steps) == ["qa1"]


def test_non_auth_templates_ignored() -> None:
    steps = [{"api": {"headers": {"a": "${var.qty}", "b": "${service.fin.base}"}}}]
    assert scan_auth_aliases(steps) == []


def test_malformed_ignored() -> None:
    steps = [{"api": {"headers": {"a": "${auth.}", "b": "${auth.###}"}}}]
    assert scan_auth_aliases(steps) == []


def test_empty_steps() -> None:
    assert scan_auth_aliases([]) == []
