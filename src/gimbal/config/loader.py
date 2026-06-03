"""config/loader.py
路径: BASE_DIR + \\src\\gimbal\\config
ConfigLoader: 多来源配置合并, 产出不可变的 BootstrapConfig。

来源优先级（高 → 低）：
  1. CLI 参数          —— CLIContext 字段（用户显式传入，最高权威）
  2. 环境变量          —— GIMBAL_* 前缀（CI/CD 注入，覆盖文件配置）
  3. mode 配置文件     —— ./mode/{mode}.yml
  4. env 配置文件      —— ./env/gimbal_{env}.yml
  5. gimbal.yaml       —— 项目级基础配置
  6. 内置默认值        —— 代码里定义的兜底值

合并规则：
  - 高优先级来源的非 None 值覆盖低优先级
  - 环境变量在 env/mode 文件路径确定之前先行加载，确保 GIMBAL_ENV/GIMBAL_MODE 生效
  - extras 字段做浅层合并（dict.update），而非整体替换
  # 路径符号转换
"""
from __future__ import annotations

import logging
import os
import yaml
from pathlib import Path
from typing import Any
from .models import BootstrapConfig
from gimbal.cli.context import CLIContext

from gimbal.log import get_logger
logger = get_logger(__name__)


# 环境变量名 → BootstrapConfig 字段名 的映射
_ENV_MAP: dict[str, str] = {
    "GIMBAL_ENV":            "env",
    "GIMBAL_MODE":           "mode",
    "GIMBAL_LOG_LEVEL":      "log_level",
    "GIMBAL_MONGO_URI":      "mongo_uri",
    "GIMBAL_MINIO_ENDPOINT": "minio_endpoint",
    "GIMBAL_REPORT_DIR":     "report_dir",
}
RELATIVE_PATH = "src\\gimbal\\config"


class ConfigLoadError(Exception):
    """配置加载异常，包含清晰的上下文信息。"""

    def __init__(self, stage: str, source: str, original_error: Exception):
        self.stage = stage
        self.source = source
        self.original_error = original_error
        super().__init__(
            f"配置加载失败 - 阶段: {stage}, 来源: {source}\n"
            f"原因: {type(original_error).__name__}: {original_error}"
        )


class ConfigLoader:
    """多来源配置加载器。

    用法::

        cfg = ConfigLoader().load(cli_ctx)
        # cfg 是 BootstrapConfig，frozen，可安全传递
    """


    def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
        """执行完整的多来源合并，返回 BootstrapConfig。

        加载顺序（低 → 高，后者覆盖前者）：
          内置默认值 → gimbal.yaml → env 文件 → mode 文件 → 环境变量 → CLI 参数

        注意：环境变量和 CLI 参数在确定 env/mode 文件路径时会提前读取，
        以保证 GIMBAL_ENV / GIMBAL_MODE / --env / --mode 能正确选到对应文件。
        """
        # 配置根路径
        BASE_DIR = self._find_base_dir()
        
        # Step 1: 内置默认值
        merged = self._load_defaults()

        # Step 2: gimbal.yaml（项目基础配置）
        merged = self._merge(merged, self._load_yaml_file(Path(f"{BASE_DIR}\\{RELATIVE_PATH}\\gimbal.yaml"), "gimbal.yaml"))

        # --- 提前收集 env/mode 的最终决议值 ---
        # 优先级：CLI > 环境变量 > 已合并配置
        # 目的：让 GIMBAL_ENV / --env 等参数能影响后续文件路径的选取
        env_vars = self._load_env()
        cli_cfg  = self._from_cli(cli_ctx)

        effective_env  = cli_cfg.get("env")  or env_vars.get("env")  or merged.env
        effective_mode = cli_cfg.get("mode") or env_vars.get("mode") or merged.mode

        # Step 3: env 配置文件
        if effective_env:
            env_path = Path(f"{BASE_DIR}\\{RELATIVE_PATH}\\env\\gimbal_{effective_env}.yml")
            merged = self._merge(merged, self._load_yaml_file(env_path, f"{effective_env}"))

        # Step 4: mode 配置文件
        if effective_mode:
            mode_path = Path(f"{BASE_DIR}\\{RELATIVE_PATH}\\mode\\{effective_mode}.yml")
            merged = self._merge(merged, self._load_yaml_file(mode_path, f"{effective_mode}"))

        # Step 5: 环境变量
        merged = self._merge(merged, env_vars)
        # Step 6: CLI 参数（最高优先级）
        merged = self._merge(merged, cli_cfg)

        return self._merge(merged, {"base_dir" : BASE_DIR})
    # ── 各来源加载 ────────────────────────────────────────────────────────────

    def _load_defaults(self) -> BootstrapConfig:
        """加载内置默认值，失败时抛出 ConfigLoadError。"""
        try:
            cfg = BootstrapConfig.model_validate(self._defaults())
            logger.debug("[ConfigLoader] 内置默认值加载成功")
            return cfg
        except Exception as e:
            raise ConfigLoadError("内置默认值", "defaults", e)

    def _load_yaml_file(self, path: Path, label: str) -> dict[str, Any]:
        """读取单个 YAML 文件，返回 dict。文件不存在时返回空 dict（非错误）。"""
        if not path.exists():
            logger.warning("[ConfigLoader] 配置文件不存在，跳过: {}", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            logger.debug("[ConfigLoader] 已加载配置文件: {}", path)
            # safe_load 在空文件时返回 None
            return data or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError("YAML解析", label, e)
        except OSError as e:
            raise ConfigLoadError("文件读取", label, e)

    def _load_env(self) -> dict[str, Any]:
        """从环境变量读取配置（GIMBAL_* 前缀）。"""
        result: dict[str, Any] = {}
        for env_key, field_name in _ENV_MAP.items():
            val = os.environ.get(env_key)
            if val is not None:
                result[field_name] = self._coerce_env(field_name, val)
                logger.debug("[ConfigLoader] 环境变量 {}={} → {}", env_key, val, field_name)
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
        if cli.mode is not None:
            result["mode"] = cli.mode
        if cli.log_level is not None:
            result["log_level"] = cli.log_level
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

    @staticmethod
    def _merge(base: BootstrapConfig, override: dict[str, Any]) -> BootstrapConfig:
        """用 override 中的非 None 值覆盖 base。

        extras 字段做浅层合并（base.extras 优先被 override.extras 更新），
        其余字段直接替换。
        """
        if not override:
            return base
        result = base.model_dump()
        for k, v in override.items():
            if v is None:
                continue
            # extras 做增量合并，避免不同来源的 key 互相覆盖
            # if k == "extras" and isinstance(v, dict) and isinstance(result.get("extras"), dict):
            #     result["extras"] = {**result["extras"], **v}
            else:
                result[k] = v
        try:
            return BootstrapConfig.model_validate(result) 

        except Exception as e:
            raise ConfigLoadError("配置校验", "merge", e)

    @staticmethod
    def _defaults() -> dict[str, Any]:
        """内置默认值。"""
        return {
            "env":               "dev",
            "mode":              "default",
            "log_level":         "info",
            "no_color":          False,
            # "mongo_uri":         "mongodb://localhost:27017",
            # "minio_endpoint":    "localhost:9000",
            "framework_version": "0.1.0",
            "plugins":           [],
            "plugins_dir":       "plugins",
            "plugin_configs":    {},
            "fail_fast":         False,
            "reporters":         ["console"],
            "report_dir":        "./reports",
            "default_timeout":   300,
            "default_retry":     0,
            "extras":            {},
        }

    @staticmethod
    def _coerce_env(field: str, raw: str) -> Any:
        """把环境变量字符串转换为目标类型。"""
        bool_fields = {"no_color", "fail_fast"}
        int_fields  = {"default_timeout", "default_retry"}
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
    def _find_base_dir() -> Path:
        """从当前目录向上逐级查找 gimbal.yaml，返回其所在目录。
        
        查找顺序：cwd → parent → ... → 文件系统根目录
        找不到时回退到 cwd，并输出 warning。
        """
        current = Path.cwd()
        for directory in [current, *current.parents]:
            if (directory / "pyproject.toml").exists():
                logger.warning("[ConfigLoader] 项目根目录: {}", directory)
                return directory
        logger.warning(
            "[ConfigLoader] 未找到 gimbal.yaml（已遍历至 {}），使用当前目录: {}",
            current.anchor,   # 文件系统根，Windows 是 C:\，Linux 是 /
            current,
        )
        return current