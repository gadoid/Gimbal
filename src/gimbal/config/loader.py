"""config/loader.py

ConfigLoader：多来源配置合并，产出不可变的 FrameworkConfig。

来源优先级（高 → 低）：
  1. CLI 参数          —— CLIContext 字段（用户显式传入，最高权威）
  2. 环境变量          —— GIMBAL_* 前缀（CI/CD 注入，覆盖文件配置）
  3. gimbal.yaml       —— 项目级配置文件，按 profile 选取对应 section
  4. 内置默认值        —— 代码里定义的兜底值

合并规则：
  - 高优先级来源的非 None 值覆盖低优先级
  - gimbal.yaml 先合并 default section，再用 profile section 覆盖
  - 环境变量只覆盖同名字段，不新增字段
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gimbal.cli.context import CLIContext

logger = logging.getLogger(__name__)

# 环境变量前缀
_ENV_PREFIX = "GIMBAL_"

# 环境变量名 → FrameworkConfig 字段名 的映射
_ENV_MAP: dict[str, str] = {
    "GIMBAL_ENV":            "env",
    "GIMBAL_PROFILE":        "profile",
    "GIMBAL_LOG_LEVEL":      "log_level",
    "GIMBAL_MONGO_URI":      "mongo_uri",
    "GIMBAL_MINIO_ENDPOINT": "minio_endpoint",
    "GIMBAL_REPORT_DIR":     "report_dir",
}


@dataclass(frozen=True)
class FrameworkConfig:
    """所有配置来源合并后的不可变快照。

    frozen=True：产出后任何层都不能修改，只能读。
    需要"修改"配置的场景（例如单测覆盖某个字段）应重新调用 ConfigLoader。
    """
    # ── 运行环境 ──────────────────────────────────────────
    env: str = "dev"
    profile: str = "default"

    # ── 日志与输出 ────────────────────────────────────────
    log_level: str = "info"
    verbose: bool = False
    no_color: bool = False

    # ── 存储后端 ──────────────────────────────────────────
    mongo_uri: str = "mongodb://localhost:27017"
    minio_endpoint: str = "localhost:9000"

    # ── 框架元信息 ────────────────────────────────────────
    framework_version: str = "0.1.0"
    plugins: tuple[str, ...] = field(default_factory=tuple)

    # ── 执行控制 ──────────────────────────────────────────
    fail_fast: bool = False
    reporters: tuple[str, ...] = field(default_factory=lambda: ("console",))
    report_dir: str = "./reports"
    default_timeout: int = 300      # 单用例默认超时（秒）
    default_retry: int = 0

    # ── 透传字段（子命令专属参数，不在 schema 里定义的） ──
    extras: dict[str, Any] = field(default_factory=dict)


class ConfigLoader:
    """多来源配置加载器。

    用法::

        cfg = ConfigLoader().load(cli_ctx)
        # cfg 是 FrameworkConfig，frozen，可安全传递
    """

    def load(self, cli_ctx: CLIContext) -> FrameworkConfig:
        """执行完整的多来源合并，返回 FrameworkConfig。"""

        # Step 1: 内置默认值（最低优先级，作为 base）
        merged: dict[str, Any] = self._defaults()

        # Step 2: gimbal.yaml（覆盖默认值）
        if cli_ctx.config_file:
            file_cfg = self._load_yaml(
                Path(cli_ctx.config_file),
                # profile 此时用 CLI 传的值，但 CLI 可能是 "default"
                # 用 CLI > 环境变量 > "default" 的顺序决定 profile
                profile=self._resolve_profile(cli_ctx),
            )
            merged = self._merge(merged, file_cfg)
        else:
            # 没有显式指定，按约定路径自动发现（找到第一个即止）
            candidate = self._discover_config_file()
            if candidate:
                profile = self._resolve_profile(cli_ctx)
                file_cfg = self._load_yaml(candidate, profile)
                merged = self._merge(merged, file_cfg)
                logger.debug("[ConfigLoader] 自动发现配置文件: %s", candidate)

        # Step 3: 环境变量（覆盖文件配置）
        env_cfg = self._load_env()
        merged = self._merge(merged, env_cfg)

        # Step 4: CLIContext 字段（最高优先级，覆盖一切）
        cli_cfg = self._from_cli(cli_ctx)
        merged = self._merge(merged, cli_cfg)

        # Step 5: 产出不可变对象
        return self._to_config(merged)

    # ── 各来源加载 ────────────────────────────────────────────────────────────

    def _defaults(self) -> dict[str, Any]:
        """内置默认值。"""
        return {
            "env":               "dev",
            "profile":           "default",
            "log_level":         "info",
            "verbose":           False,
            "no_color":          False,
            "mongo_uri":         "mongodb://localhost:27017",
            "minio_endpoint":    "localhost:9000",
            "framework_version": "0.1.0",
            "plugins":           [],
            "fail_fast":         False,
            "reporters":         ["console"],
            "report_dir":        "./reports",
            "default_timeout":   300,
            "default_retry":     0,
            "extras":            {},
        }

    def _load_yaml(self, path: Path, profile: str) -> dict[str, Any]:
        """读取 gimbal.yaml，合并 default + profile section。

        文件结构约定：
            default:
              mongo_uri: mongodb://localhost:27017
              plugins: []
            dev:
              mongo_uri: mongodb://dev-server:27017
            prod:
              plugins: [allure, platform_uploader]
              report_dir: /data/reports
        """
        try:
            import yaml
            raw: dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("[ConfigLoader] 读取配置文件失败 %s: %s", path, exc)
            return {}

        base = dict(raw.get("default", {}))
        if profile and profile != "default":
            profile_cfg = raw.get(profile, {})
            if not profile_cfg:
                logger.warning("[ConfigLoader] profile '%s' 在 %s 中不存在", profile, path)
            base.update(profile_cfg)

        logger.debug("[ConfigLoader] 从 %s 加载 profile=%s: %s", path, profile, list(base.keys()))
        return base

    def _load_env(self) -> dict[str, Any]:
        """从环境变量读取配置（GIMBAL_* 前缀）。"""
        result: dict[str, Any] = {}
        for env_key, field_name in _ENV_MAP.items():
            val = os.environ.get(env_key)
            if val is not None:
                result[field_name] = self._coerce_env(field_name, val)
                logger.debug("[ConfigLoader] 环境变量 %s=%s → %s", env_key, val, field_name)
        return result

    def _from_cli(self, cli: CLIContext) -> dict[str, Any]:
        """从 CLIContext 提取字段，None 值不参与覆盖。

        CLIContext.extras 里约定可以携带子命令的执行控制参数：
            fail_fast, reporters, report_dir, default_timeout, default_retry
        """
        result: dict[str, Any] = {}

        # 框架级字段（直接映射）
        if cli.env is not None:
            result["env"] = cli.env
        if cli.profile is not None:
            result["profile"] = cli.profile
        if cli.log_level is not None:
            # verbose 比 log_level 优先级更高
            result["log_level"] = "debug" if cli.verbose else cli.log_level
        if cli.verbose:
            result["verbose"] = True
        if cli.no_color:
            result["no_color"] = True

        # extras 中的执行控制参数（由各 CLI 子命令注入）
        extras = dict(cli.extras)
        for key in ("fail_fast", "reporters", "report_dir", "default_timeout", "default_retry"):
            if key in extras:
                result[key] = extras.pop(key)

        # 剩余 extras 透传
        if extras:
            result["extras"] = extras

        return result

    # ── 辅助 ─────────────────────────────────────────────────────────────────

    def _discover_config_file(self) -> "Path | None":
        """按约定路径查找配置文件，返回第一个存在的路径。

        查找优先级：
          1. GIMBAL_CONFIG 环境变量（CI/CD 场景，明确指定）
          2. $PWD/gimbal.yaml  /  $PWD/gimbal.yml（项目级，最常用）
          3. ~/.gimbal/config.yaml               （用户全局，兜底）
        """
        env_path = os.environ.get("GIMBAL_CONFIG")
        if env_path:
            p = Path(env_path)
            if p.exists():
                return p
            logger.warning("[ConfigLoader] GIMBAL_CONFIG 指定的文件不存在: %s", env_path)

        for name in ("gimbal.yaml", "gimbal.yml"):
            p = Path.cwd() / name
            if p.exists():
                return p

        user_cfg = Path.home() / ".gimbal" / "config.yaml"
        if user_cfg.exists():
            return user_cfg

        return None

    def _resolve_profile(self, cli: CLIContext) -> str:
        """决定最终使用的 profile（CLI > 环境变量 > 默认）。"""
        if cli.profile and cli.profile != "default":
            return cli.profile
        env_profile = os.environ.get("GIMBAL_PROFILE")
        if env_profile:
            return env_profile
        return cli.profile or "default"

    @staticmethod
    def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """用 override 中的非 None 值覆盖 base，不修改原始 dict。"""
        result = dict(base)
        for k, v in override.items():
            if v is not None:
                result[k] = v
        return result

    @staticmethod
    def _coerce_env(field: str, raw: str) -> Any:
        """把环境变量字符串转换为目标类型。"""
        bool_fields = {"verbose", "no_color", "fail_fast"}
        int_fields = {"default_timeout", "default_retry"}
        list_fields = {"plugins", "reporters"}

        if field in bool_fields:
            return raw.lower() in ("1", "true", "yes")
        if field in int_fields:
            try:
                return int(raw)
            except ValueError:
                return raw
        if field in list_fields:
            return [s.strip() for s in raw.split(",") if s.strip()]
        return raw

    @staticmethod
    def _to_config(merged: dict[str, Any]) -> FrameworkConfig:
        """dict → FrameworkConfig，做类型规整。"""
        # list → tuple（frozen dataclass 字段）
        plugins = tuple(merged.get("plugins") or [])
        reporters = tuple(merged.get("reporters") or ["console"])

        return FrameworkConfig(
            env=merged.get("env", "dev"),
            profile=merged.get("profile", "default"),
            log_level=merged.get("log_level", "info"),
            verbose=bool(merged.get("verbose", False)),
            no_color=bool(merged.get("no_color", False)),
            mongo_uri=merged.get("mongo_uri", "mongodb://localhost:27017"),
            minio_endpoint=merged.get("minio_endpoint", "localhost:9000"),
            framework_version=merged.get("framework_version", "0.1.0"),
            plugins=plugins,
            fail_fast=bool(merged.get("fail_fast", False)),
            reporters=reporters,
            report_dir=merged.get("report_dir", "./reports"),
            default_timeout=int(merged.get("default_timeout", 300)),
            default_retry=int(merged.get("default_retry", 0)),
            extras=dict(merged.get("extras") or {}),
        )