"""``/full`` resource contract (ADR 0002 §D-D5).

M6 mapping for the full-contract surface:
    GET /api/resource/full                 → list
    GET /api/resource/{id}/full            → detail
    GET /api/systems/{system}/resource/full             → list_for_system
    GET /api/systems/{system}/resource/{id}/full        → detail_for_system

Light :class:`ResourceView` only exposes ``name`` / ``kind`` (resource payloads
may carry credentialed ``config`` blobs). ``/full`` re-emits the entire
:class:`ResourceUnion` under the ``extra`` key, surfacing ``image`` /
``config`` / ``portMapping`` for platform resource editors.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# Seeded by conftest.py: ``res_idx.register(fin_resource_template(),
# item_id=f"{FIN_SYSTEM}.tidb_test")``.
RESOURCE_ID = "fin.tidb_test"


# ── /api/resource/{id}/full ─────────────────────────────────────────


def test_resource_full_exposes_extra(http_client: TestClient) -> None:
    """``/full`` exposes ``extra`` carrying ``image`` / ``config`` / ``portMapping``."""
    resp = http_client.get(f"/api/resource/{RESOURCE_ID}/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "resource"
    item = body["data"]["item"]

    # Light always exposes ``name`` / ``kind``; full ALSO has ``extra``.
    assert item["name"] == RESOURCE_ID
    assert item["kind"] in {"mock", "file", "mock_ref", "file_ref"}
    assert "extra" in item and isinstance(item["extra"], dict)


def test_resource_full_extra_carries_resource_payload(
    http_client: TestClient,
) -> None:
    """The bundled Mock resource seeds ``image`` / ``config`` / ``portMapping``."""
    resp = http_client.get(f"/api/resource/{RESOURCE_ID}/full")
    item = resp.json()["data"]["item"]
    extra = item["extra"]
    # The bundled Mock fixture registers all three keys.
    assert "image" in extra, f"expected image in extra, got keys={list(extra.keys())}"
    assert "config" in extra, f"expected config in extra, got keys={list(extra.keys())}"
    assert "portMapping" in extra, f"expected portMapping in extra, got keys={list(extra.keys())}"
    # Image is a docker-style image string.
    assert "/" in extra["image"]


def test_resource_full_light_excludes_extra(http_client: TestClient) -> None:
    """The light ``/api/resource/{id}`` does NOT expose ``extra``."""
    resp = http_client.get(f"/api/resource/{RESOURCE_ID}")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert "extra" not in item
    # Light contract is strictly {name, kind}.
    assert set(item.keys()) == {"name", "kind"}


def test_resource_full_unknown_id_returns_404(http_client: TestClient) -> None:
    resp = http_client.get("/api/resource/no.such.resource/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"


# ── /api/resource/full ─────────────────────────────────────────────


def test_resource_full_list_shape(http_client: TestClient) -> None:
    resp = http_client.get("/api/resource/full")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    items = body["data"]["items"]
    # Bundled fin seed registers exactly 1 resource.
    assert body["data"]["total"] == len(items) >= 1
    # Every item has the full {name, kind, extra} shape.
    for it in items:
        assert "name" in it and "kind" in it and "extra" in it


# ── system-scoped ──────────────────────────────────────────────────


def test_resource_full_for_system(http_client: TestClient) -> None:
    resp = http_client.get("/api/systems/fin/resource/full")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert any(it["name"] == RESOURCE_ID for it in items)


def test_resource_full_for_system_single(http_client: TestClient) -> None:
    resp = http_client.get(f"/api/systems/fin/resource/{RESOURCE_ID}/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["name"] == RESOURCE_ID
    assert "extra" in item
    assert "image" in item["extra"]


def test_resource_full_for_system_unknown_id_returns_404(
    http_client: TestClient,
) -> None:
    resp = http_client.get("/api/systems/fin/resource/no.such/full")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "dim_item_not_found"