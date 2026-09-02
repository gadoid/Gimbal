"""Application configuration via pydantic-settings."""
from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


def _generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


# 后端根(app/ 的上一级 = backend/):所有相对资源锚定于此,而非进程 CWD。
# 从仓库根误启动会在根部 mkdir 空 data/ + 新建空库,服务"静默失忆"
# (2026-09-02 实录:根部冒出第二个空 app.db,登录全 401)。
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET: str = ""
    JWT_ALGO: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # ── Fernet ────────────────────────────────────────────
    FERNET_KEY: str = ""

    # ── DB ────────────────────────────────────────────────
    # 锚定 backend/(见 _BACKEND_ROOT):误启动目录不再另起炉灶。
    DATABASE_URL: str = (
        f"sqlite+aiosqlite:///{(_BACKEND_ROOT / 'data' / 'app.db').as_posix()}"
    )

    # ── Data dir ──────────────────────────────────────────
    # Resolved to absolute at startup so JSONL run-log / DB paths
    # never land as relative ``./data\...`` in logs.
    DATA_DIR: Path = _BACKEND_ROOT / "data"
    # case 案卷(result.json/case.json,含注入后明文凭证)保留天数;
    # 启动期清扫超期目录。0 = 禁用清扫(P2:此前无限累积)。
    CASE_RETENTION_DAYS: int = 14

    # ── Gimbal 执行链(V3.2 ``gimbal run launch`` 子进程) ──
    # GIMBAL_BIN: gimbal 可执行文件(如 D:\Gimbal\Scripts\gimbal.exe);
    # 空值回退同解释器 ``python -m gimbal``(同 venv 部署最稳)。
    GIMBAL_BIN: str = ""
    # 单次 launch 子进程超时(秒)。
    GIMBAL_TIMEOUT_SEC: float = 300.0
    # P7 资源闸:单次执行总行数上限(行数 × nRuns,409 拒单)与
    # 进程内 launch 子进程同时在飞上限(跨 execution 合并生效)。
    MAX_RUNS_PER_EXECUTION: int = 200
    MAX_CONCURRENT_LAUNCHES: int = 8
    # ── Gimbal 插件注入(透传给执行子进程;空值 = 现状零变化) ──
    # GIMBAL_PLUGINS_DIR:文件系统插件目录(绝对路径;空 = 引擎默认 base_dir/plugins)
    GIMBAL_PLUGINS_DIR: str = ""
    # GIMBAL_PLUGINS:插件白名单,逗号分隔(空 = 引擎侧全部启用)
    GIMBAL_PLUGINS: str = ""
    # GIMBAL_PLUGIN_CONFIGS:按插件名配置,JSON 串(空 = 全走插件 default_config)
    GIMBAL_PLUGIN_CONFIGS: str = ""

    # ── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Plate integration (V3 scenario composer) ──────────
    # Base URL of the gimbal-plate FastAPI service.  Default port 8765 to
    # stay out of Platform's 8000 + Vite's 5173 footprint.
    PLATE_BASE_URL: str = "http://127.0.0.1:8765"
    PLATE_TIMEOUT_SEC: float = 30.0
    # 连续 PlateUnavailable 达到该次数后熔断:本轮 fan-out 剩余行不再
    # 调用 plate,直接记 plate_unavailable(P6:plate 宕机时避免逐行
    # 全超时等待)。
    PLATE_BREAKER_THRESHOLD: int = 3

    # Set in model_post_init — True when the corresponding secret was
    # freshly generated because env/.env didn't provide one.  Not part of
    # the serialized settings; read-only diagnostics for the startup
    # warning in main.lifespan.
    JWT_SECRET_EPHEMERAL: bool = False
    FERNET_KEY_EPHEMERAL: bool = False

    def model_post_init(self, __context) -> None:
        # Ephemeral-key flags: True when the secret was freshly generated
        # because the env/.env didn't provide one.  A restart then rotates
        # the key (all JWT sessions invalidated / all Fernet ciphertexts
        # undecryptable) — the app logs a loud warning at startup (see
        # main.lifespan) so operators notice instead of debugging phantom
        # "401 every morning" incidents.
        self.JWT_SECRET_EPHEMERAL = not self.JWT_SECRET
        self.FERNET_KEY_EPHEMERAL = not self.FERNET_KEY
        if not self.JWT_SECRET:
            self.JWT_SECRET = secrets.token_urlsafe(48)
        if not self.FERNET_KEY:
            self.FERNET_KEY = _generate_fernet_key()
        # Force-absolute.  pydantic-settings re-coerces from env vars which
        # may hand us back a relative ``./data``; normalize again here so
        # every downstream consumer (JSONL run logs, DB paths, UI preview)
        # sees e.g. ``D:\Gimbal\Gimbal\gimbal-platform\data\...``.
        # (tmp/ and reports/ were the retired V1 executor's paths — V3
        # only writes data/runs/<date>.jsonl, created on demand.)
        self.DATA_DIR = self.DATA_DIR.resolve()
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
