"""Manifest parser.

Reads plugin.yaml / plugin.yml / plugin.toml files and produces a PluginSpec.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any, Union

from .spec import PluginSpec
from .categories import PluginCategory

logger = logging.getLogger(__name__)


# 允许的 manifest 文件名（按优先级）
MANIFEST_FILENAMES = ("plugin.yaml", "plugin.yml", "plugin.toml")


class ManifestError(Exception):
    """manifest 解析错误。"""
    pass


def find_manifest(plugin_dir: Union[str, Path]) -> Path | None:
    """在 plugin_dir 下找 manifest 文件。"""
    p = Path(plugin_dir)
    for name in MANIFEST_FILENAMES:
        candidate = p / name
        if candidate.is_file():
            return candidate
    return None


def parse_manifest_file(path: Union[str, Path]) -> PluginSpec:
    """从 yaml/toml 解析 PluginSpec。"""
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p}")

    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        data = _parse_yaml(text)
    elif p.suffix == ".toml":
        data = _parse_toml(text)
    else:
        raise ManifestError(f"unsupported manifest format: {p.suffix}")

    if not isinstance(data, dict):
        raise ManifestError(f"manifest root must be a mapping, got {type(data).__name__}")

    return _build_spec(data, manifest_path=str(p.resolve()))


def _build_spec(data: dict[str, Any], manifest_path: str = "") -> PluginSpec:
    """从 dict 构造 PluginSpec，做必需字段校验。"""
    name = data.get("name")
    version = data.get("version")
    entry_point = data.get("entry_point")
    if not name or not isinstance(name, str):
        raise ManifestError(f"manifest missing/invalid 'name': {name!r}")
    if not version or not isinstance(version, str):
        raise ManifestError(f"manifest missing/invalid 'version': {version!r}")
    if not entry_point or not isinstance(entry_point, str):
        raise ManifestError(f"manifest missing/invalid 'entry_point': {entry_point!r}")
    if ":" not in entry_point:
        raise ManifestError(f"entry_point must be 'module:Class', got: {entry_point!r}")

    cat_raw = data.get("category", "generic")
    try:
        category = PluginCategory(cat_raw) if isinstance(cat_raw, str) else PluginCategory.GENERIC
    except ValueError:
        logger.warning("[Manifest] unknown category %r, falling back to GENERIC", cat_raw)
        category = PluginCategory.GENERIC

    deps = data.get("dependencies") or []
    if not isinstance(deps, list):
        raise ManifestError("'dependencies' must be a list")
    caps = data.get("capabilities") or []
    if not isinstance(caps, list):
        raise ManifestError("'capabilities' must be a list")

    return PluginSpec(
        name=name,
        version=version,
        entry_point=entry_point,
        category=category,
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
        homepage=str(data.get("homepage", "")),
        dependencies=[str(d) for d in deps],
        capabilities=[str(c) for c in caps],
        gimbal_version=str(data.get("gimbal_version", "")),
        config_schema=data.get("config_schema") or {},
        default_config=data.get("default_config") or {},
        manifest_path=manifest_path,
        plugin_path=str(Path(manifest_path).parent) if manifest_path else None,
        source="filesystem",
    )


# ── 格式解析器（带 try-import 容错） ───────────────────────────

def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise ManifestError(
            "PyYAML is required to parse yaml manifests. `pip install pyyaml`."
        ) from e
    return yaml.safe_load(text) or {}


def _parse_toml(text: str) -> dict[str, Any]:
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError as e:
            raise ManifestError(
                "toml parsing requires Python 3.11+ or `pip install tomli`."
            ) from e
    return tomllib.loads(text)
