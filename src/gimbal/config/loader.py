"""config/loader.py

ConfigLoader：多来源配置合并，产出不可变的 FrameworkConfig。

来源优先级（高 → 低）：
  1. CLI 参数          —— CLIContext 字段（用户显式传入，最高权威）
  2. 环境变量          —— GIMBAL_* 前缀（CI/CD 注入，覆盖文件配置）
  3. gimbal.yaml       —— 项目级配置文件，按 mode 选取对应 section
  4. 内置默认值        —— 代码里定义的兜底值

合并规则：
  - 高优先级来源的非 None 值覆盖低优先级
  - gimbal.yaml 先合并 default section，再用 mode section 覆盖
  - 环境变量只覆盖同名字段，不新增字段
"""
from __future__ import annotations

import logging
import os
import yaml
from pathlib import Path
from typing import Any
from .models import FrameworkConfig
from gimbal.cli.context import CLIContext

logger = logging.getLogger(__name__)

# 环境变量前缀
_ENV_PREFIX = "GIMBAL_"

# 环境变量名 → FrameworkConfig 字段名 的映射
_ENV_MAP: dict[str, str] = {
    "GIMBAL_ENV":            "env",
    "GIMBAL_MODE":           "mode",
    "GIMBAL_LOG_LEVEL":      "log_level",
    "GIMBAL_MONGO_URI":      "mongo_uri",
    "GIMBAL_MINIO_ENDPOINT": "minio_endpoint",
    "GIMBAL_REPORT_DIR":     "report_dir",
}

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
        # cfg 是 FrameworkConfig，frozen，可安全传递
    """

    def load(self, cli_ctx: CLIContext) -> FrameworkConfig:
        """执行完整的多来源合并，返回 FrameworkConfig。"""
        try:
            # Step 1: 内置默认值
            merged = FrameworkConfig.model_validate(self._defaults())
            logger.debug("[ConfigLoader] 内置默认值加载成功")
        except Exception as e:
            raise ConfigLoadError("内置默认值", "defaults", e)

        # Step 2: 配置文件加载
        #  加载优先级 gimbal.yaml -> env -> mode -> cli -> 环境变量
        if path := Path("gimbal.yaml").exists() :
            default_cfg = yaml.safe_load(path)
            merged = self._merge(merged,default_cfg)
        else :
            print("未找到默认配置文件，跳过默认配置加载")
    
        if cli_ctx.env and (path := Path(f"./env/gimbal_{cli_ctx.env}.yml")) :
            env_cfg = yaml.safe_load(path.read_text())
            merged = self._merge(merged,env_cfg)
        elif merged.env and (path := Path(f"./env/gimbal_{merged.env}.yml")) :
            env_cfg = yaml.safe_load(path.read_text())
            merged = self._merge(merged,env_cfg)
        else :
            print("未找到环境配置文件，跳过环境配置加载")

        if cli_ctx.mode and path := Path(f"./mode/{cli_ctx.mode}.yml") :
            mode_cfg = yaml.safe_load(path)
            merged = self._merge(merged,mode_cfg)
        elif merged.mode and path := Path(f"./mode/{cli_ctx.mode}.yml") :
            mode_cfg = yaml.safe_load(path)
            merged = self._merge(merged,mode_cfg)
        else :
            print("未找到模式配置文件，跳过模式配置加载")   

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
            "mode":           "default",
            "log_level":         "info",
            "no_color":          False,
            # "mongo_uri":         "mongodb://localhost:27017",
            # "minio_endpoint":    "localhost:9000",
            "framework_version": "0.1.0",
            "plugins":           [],
            "fail_fast":         False,
            "reporters":         ["console"],
            "report_dir":        "./reports",
            "default_timeout":   300,
            "default_retry":     0,
            "extras":            {},
        }

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
    def _merge(base: FrameworkConfig, override: dict[str, Any]) -> dict[str, Any]:
        """用 override 中的非 None 值覆盖 base，不修改原始 dict。"""
        result = base.model_dump()
        for k, v in override.items():
            if v is not None:
                result[k] = v
        return FrameworkConfig.model_validate(result)

    @staticmethod
    def _coerce_env(field: str, raw: str) -> Any:
        """把环境变量字符串转换为目标类型。"""
        bool_fields = {"no_color", "fail_fast"}
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
            mode=merged.get("mode", "default"),
            log_level=merged.get("log_level", "info"),
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