from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from ..version import getVersion
from pathlib import Path


class BootstrapConfig(BaseModel):
    """所有配置来源合并后的不可变快照。

    frozen=True：产出后任何层都不能修改，只能读。
    需要「修改」配置的场景（例如单测覆盖某个字段）应重新调用 ConfigLoader。

    注意：运行期可变状态（认证会话、token 等）由独立容器承载，不在
    BootstrapConfig 范围内。详见 gimbal.auth.registry.AuthRegistry。
    """
    base_dir : Path = Path(".")
    model_config = ConfigDict(frozen=True)

    # ── 运行环境 ──────────────────────────────────────────
    env: str = Field("dev", description="目标环境 dev|test|staging|prod")
    mode: str = Field("local", description="执行模式 local|server|service")

    services: dict = Field(default_factory=dict, description="服务域名池 {name: {base_url, timeout}}")
    connection_pool: dict = Field(default_factory=dict, description="数据库/中间件连接池 {name: {host, port, ...}}")

    # ── 日志与输出 ────────────────────────────────────────
    log_level: str = Field("info", description="日志等级 debug|info|warning|error")
    no_color: bool = Field(False, description="禁用终端颜色，CI 环境建议开启")

    # ── 框架元信息 ────────────────────────────────────────
    framework_version: str = Field(default_factory=getVersion, description="框架版本号")
    plugins: tuple[str, ...] = Field(default_factory=tuple, description="启用的插件列表（白名单；空 = 全部启用）")
    plugins_dir: str = Field("plugins", description="插件目录（相对 base_dir）")
    plugin_configs: dict[str, dict] = Field(default_factory=dict, description="按插件名配置: {plugin_name: {key: value}}")
    reporters: tuple[str, ...] = Field(default_factory=lambda: ("console",), description="启用的 reporter")
    report_dir: str = Field("reports", description="报告输出根目录")

    # ── 执行控制 ──────────────────────────────────────────
    fail_fast: bool = Field(False, description="首次失败即终止整个 suite")

    request_timeout: int | None = Field(None, description="单次 HTTP 请求超时（秒），None 不限制")
    scenario_timeout: int | None = Field(None, description="单 scenario 最大执行时间（秒），None 不限制")
    suite_timeout: int | None = Field(None, description="单 suite 最大执行时间（秒），None 不限制")

    poll_timeout: int = Field(60, description="Poll strategy 默认超时（秒）")
    poll_interval: int = Field(5, description="Poll strategy 默认检查周期（秒）")

    # ── CLI 变量注入（修复 #52 完整链路）──
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="CLI --var / --var-file 注入的 KV 变量，模板 ${var} 可引用"
    )

    # ── 新增：generator 实例（由 bootstrap() 注入）──
    # 类型用 Any 以避免 Pydantic 对 Generator 的 schema 生成（Generator 不是 BaseModel），
    # 逻辑上等价于 "Generator | None"——bootstrap() 注入的就是 Generator 实例；
    # 想要更强的类型检查可在 TYPE_CHECKING 块中引用 Generator 做 mypy 约束。
    generator: Any = Field(
        default=None,
        description="变量生成器实例（由 bootstrap() 构造并注入；未传则禁用变量生成）",
    )

    retry_count: int = Field(0, description="失败重试次数")
    retry_interval: int = Field(5, description="重试间隔（秒）")

    # ── 存储后端（暂未启用）─────────────────────────────
    # mongo_uri: str = "mongodb://localhost:27017"
    # minio_endpoint: str = "localhost:9000"


# class BootstrapConfig(BaseModel):
#     load_options: LoadOptions
#     source_options: SourceOptions
#     log_options: LogOptions
#     meta_options: MetaOptions
#     execution_options : ExecutionOptions

# class LoadOptions(BaseModel) :
#     base_dir : Path = Path(".")
#     env : str = Field("dev", description="目标环境 dev|test|staging|prod")
#     mode: str = Field("local", description="执行模式 local|server|service")


# class SourceOptions(BaseModel) :
#     services: dict = Field(default_factory=dict, description="服务域名池 {name: {base_url, timeout}}")
#     connection_pool: dict = Field(default_factory=dict, description="数据库/中间件连接池 {name: {host, port, ...}}")
#     users: dict = Field(default_factory=dict, description="测试用户池 {role: {user_name, user_pass, auth_type}}")

# class LogOptions(BaseModel) :
#     log_level: str = Field("info", description="日志等级 debug|info|warning|error")
#     no_color: bool = Field(False, description="禁用终端颜色，CI 环境建议开启")

# class MetaOptions(BaseModel) :
#     framework_version: str = Field(default_factory=getVersion, description="框架版本号")
#     plugins: tuple[str, ...] = Field(default_factory=tuple, description="启用的插件列表")
#     reporters: tuple[str, ...] = Field(default_factory=lambda: ("console",), description="启用的 reporter")
#     report_dir: str = Field("reports", description="报告输出根目录")


# class ExecutionOptions(BaseModel) :
#     fail_fast: bool = Field(False, description="首次失败即终止整个 suite")

#     request_timeout: int | None = Field(None, description="单次 HTTP 请求超时（秒），None 不限制")
#     scenario_timeout: int | None = Field(None, description="单 scenario 最大执行时间（秒），None 不限制")
#     suite_timeout: int | None = Field(None, description="单 suite 最大执行时间（秒），None 不限制")

#     poll_timeout: int = Field(60, description="Poll strategy 默认超时（秒）")
#     poll_interval: int = Field(5, description="Poll strategy 默认检查周期（秒）")

#     retry_count: int = Field(0, description="失败重试次数")
#     retry_interval: int = Field(5, description="重试间隔（秒）")