"""Application configuration via pydantic-settings."""
from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


def _generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # ── Data dir ──────────────────────────────────────────
    # Resolved to absolute at startup so JSONL run-log / DB paths
    # never land as relative ``./data\...`` in logs.
    DATA_DIR: Path = Path("./data").resolve()
    # case 案卷(result.json/case.json,含注入后明文凭证)保留天数;
    # 启动期清扫超期目录。0 = 禁用清扫(P2:此前无限累积)。
    CASE_RETENTION_DAYS: int = 14

    # ── Gimbal 执行链(V3.2 ``gimbal run launch`` 子进程) ──
    # GIMBAL_BIN: gimbal 可执行文件(如 D:\Gimbal\Scripts\gimbal.exe);
    # 空值回退同解释器 ``python -m gimbal``(同 venv 部署最稳)。
    GIMBAL_BIN: str = ""
    # 单次 launch 子进程超时(秒)。
    GIMBAL_TIMEOUT_SEC: float = 300.0

    # ── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Plate integration (V3 scenario composer) ──────────
    # Base URL of the gimbal-plate FastAPI service.  Default port 8765 to
    # stay out of Platform's 8000 + Vite's 5173 footprint.
    PLATE_BASE_URL: str = "http://127.0.0.1:8765"
    PLATE_TIMEOUT_SEC: float = 30.0

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
